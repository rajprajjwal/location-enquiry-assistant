"""Run the locked Activity 14 implementation once on all 80 unchanged frozen inputs."""
from collections import Counter
from contextlib import closing
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
import traceback

import shutil
BUNDLE = Path(__file__).resolve().parents[1]
REPO = next(p for p in BUNDLE.parents if (p / 'data/ground-truth.xlsx').is_file())
OUT = BUNDLE / 'verification-output'
OUT.mkdir(exist_ok=True)
for name in ['run-manifest.json', 'review-cases.json', 'locked-gold.json', 'inputs.jsonl', 'ground-truth-frozen.csv', 'fact-alignment-plan.json']:
    if not (OUT / name).exists():
        shutil.copy2(BUNDLE / name, OUT / name)
PRIOR = BUNDLE / 'historical-baseline' 
MANIFEST = json.loads((OUT / 'run-manifest.json').read_text())
MANIFEST['runtime'] = str(BUNDLE / 'runtime')
sys.path.insert(0, MANIFEST['runtime'])
import copilot
from copilot.case_storage import cases
from copilot.case_storage.db import connect
from copilot.enquiry_workflow.cases import run_case
from copilot.enquiry_workflow.retrieval import rag_document_search
from copilot.model_gateway.client import LLMClient, LLMError
from copilot.response_drafting.schemas import validate_outputs
from copilot.safety.pii import redact

REPLIES = {'provider': 'Mapbox', 'current_provider': 'Mapbox', 'region': 'Germany',
           'monthly_volume': '500,000 requests per month', 'timeline': 'June',
           'api': 'Directions', 'use_case_api': 'Directions',
           'providers': 'Google Maps Platform and Mapbox', 'budget': 'USD 500',
           'technical_constraints': 'Web application'}


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def snapshot(con, result):
    cid = result['case_id']
    state = cases.load_state(con, cid)
    output = result['outputs']
    memory = result['conversation_state']
    assert state['last_result']['outputs'] == output
    return {
        'route': result['status'], 'next_action': output.get('next_action'),
        'owner': output.get('responsible_role'),
        'approvals': [{k: p[k] for k in ('type', 'payload', 'status')} for p in cases.list_pending(con, cid)],
        'proposed_actions': result.get('proposed_actions', []),
        'active_questions': result['clarifying_questions'],
        'pending_reply': state.get('pending_clarification'),
        'asked': memory['questions_asked'], 'answered': memory['questions_answered'],
        'awaiting': [issue for issue in memory['unresolved_issues'] if issue.startswith('Awaiting ')],
        'clarification_messages': [x['content'] for x in cases.get_case_history(con, cid) if x['role'] == 'clarification'],
    }


def output_record(result):
    keys = ['status', 'outputs', 'response_draft', 'clarifying_questions', 'proposed_actions',
            'steps', 'step_count', 'critic', 'tool_calls', 'route_evidence',
            'follow_up_selection', 'diagnostic_context', 'qualification_plan_validation',
            'qualification_plan_error', 'diagnostic_plan_error', 'reliability', 'conversation_state']
    return {key: result.get(key) for key in keys}


def request_key(messages, options):
    normalized = []
    for item in messages:
        message = dict(item)
        content = message.get('content')
        if isinstance(content, str):
            try:
                # JSON object key order is immaterial to the captured data contract.
                decoded = json.loads(content)
                if isinstance(decoded, (dict, list)):
                    message['content'] = decoded
            except ValueError:
                pass
        normalized.append(message)
    settings = {k: v for k, v in options.items() if k != 'messages'}
    return sha256(json.dumps({'messages': normalized, 'options': settings}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Client:
    def __init__(self):
        self.record_id = None
        self.turn = 'initial'
        self.calls = self.errors = 0
        self.cache_hits = 0
        self.offsets = {}
        self.records = {}
        for record in rows(BUNDLE / 'model-calls.jsonl'):
            if 'error_type' in record:
                raise RuntimeError('This replay expects the recorded error-free run.')
            key = (record['record_id'], record['turn'], request_key(record['messages'], record['options']))
            self.records.setdefault(key, []).append(record['response'])

    def complete(self, *args, **kwargs):
        from copilot.model_gateway.client import Completion
        messages = args[0] if args else kwargs.get('messages', [])
        key = (self.record_id, self.turn, request_key(messages, kwargs))
        offset = self.offsets.get(key, 0)
        choices = self.records.get(key, [])
        if offset >= len(choices):
            raise RuntimeError('Uncaptured model request refused.')
        self.offsets[key] = offset + 1
        self.cache_hits += 1
        return Completion(**choices[offset])


def one_case(case, reference, previous, client, search):
    start = perf_counter()
    client.record_id = case['record_id']
    client.turn = 'initial'
    error = None
    resumed = {'baseline': previous['reopened']['integrated']} if 'integrated' in previous.get('reopened', {}) else {}
    followup = None
    with TemporaryDirectory(prefix='activity14-frozen-locked-') as temp:
        path = Path(temp) / 'case.db'
        with closing(connect(path)) as con:
            cid = cases.create_case(con)
            for turn in case['history']:
                cases.add_message(con, cid, turn['role'], turn['text'])
            result = run_case(con, case['query'], case_id=cid, client=client, search=search,
                              diagnostic_planning=True)
            schema_errors = validate_outputs(result['outputs'])
            current = snapshot(con, result)
            actual = result['outputs'].get('clarifying_questions', {}).get('questions', [])
            questions = [q.get('text', '') if isinstance(q, dict) else str(q) for q in actual]
            details = {'status': result['status'], 'selection': result.get('follow_up_selection'),
                       'diagnostic_context': result.get('diagnostic_context'),
                       'restored_diagnostic_state': result['conversation_state'].get('diagnostic_state')}
            complete = output_record(result)
            pending = current['pending_reply']
        if pending and pending['field'] in REPLIES:
            client.turn = 'reply'
            with closing(connect(path)) as con:
                reply = REPLIES[pending['field']]
                result = run_case(con, reply, case_id=cid, client=client, search=search,
                                  diagnostic_planning=True)
                resumed['integrated'] = snapshot(con, result)
                followup = {'query': reply, 'result': output_record(result),
                            'schema_errors': validate_outputs(result['outputs'])}
        elif pending:
            followup = {'not_run': 'No predefined synthetic reply for this pending field.', 'field': pending['field']}
    baseline = previous['snapshots']['integrated']
    reply_changes = ({key: {'before': value, 'after': resumed['integrated'][key]}
                      for key, value in resumed['baseline'].items() if value != resumed['integrated'][key]}
                     if set(resumed) == {'baseline', 'integrated'} else {})
    return {'record_id': case['record_id'], 'bucket': reference['bucket'], 'cohort': 'frozen80',
            'query': case['query'], 'history': case['history'], 'gold': reference['questions'],
            'questions': {'baseline': previous['questions']['integrated'], 'integrated': questions},
            'snapshots': {'baseline': baseline, 'integrated': current},
            'details': {'baseline': previous['details']['integrated'], 'integrated': details},
            'preserved': {key: baseline[key] == current[key] for key in baseline},
            'current_result': complete, 'schema_errors': schema_errors,
            'reopened': resumed, 'followup': followup,
            'reply_preserved': resumed['baseline'] == resumed['integrated'] if set(resumed) == {'baseline', 'integrated'} else None,
            'reply_changes': reply_changes, 'duration_ms': round((perf_counter() - start) * 1000),
            'execution_error': error}


def verify_lock():
    runtime = Path(MANIFEST['runtime'])
    assert Path(copilot.__file__).resolve().parent == runtime / 'copilot'
    assert not os.environ.get('TRACKB_GT_CSV'), 'Frozen interpretation must stay zero-shot.'
    assert all(digest(runtime / p) == h for p, h in MANIFEST['source_hashes'].items())
    assert digest(OUT / 'locked-gold.json') == MANIFEST['gold_sha256']
    assert digest(OUT / 'review-cases.json') == MANIFEST['case_sha256']
    assert digest(OUT / 'inputs.jsonl') == MANIFEST['frozen_inputs_sha256']
    assert digest(OUT / 'ground-truth-frozen.csv') == MANIFEST['frozen_gt_sha256']
    assert digest(OUT / 'fact-alignment-plan.json') == MANIFEST['evaluation_alignment_plan_sha256']
    assert digest(PRIOR / 'predictions.jsonl') == MANIFEST['prior_predictions_sha256']
    assert digest(REPO / 'data/ground-truth.xlsx') == MANIFEST['workbook_before_sha256']


def main():
    verify_lock()
    packet = json.loads((OUT / 'review-cases.json').read_text())
    labels = {r['record_id']: r for r in json.loads((OUT / 'locked-gold.json').read_text())['cases']}
    prior = {r['record_id']: r for r in rows(PRIOR / 'predictions.jsonl')}
    assert len(packet) == len(labels) == len(prior) == 80
    assert [r['record_id'] for r in packet] == MANIFEST['frozen_record_ids']
    output = OUT / 'predictions.jsonl'
    finished = rows(output)
    seen = {r['record_id'] for r in finished}
    assert len(finished) == len(seen) and seen <= labels.keys()
    assert [r['record_id'] for r in finished] == MANIFEST['frozen_record_ids'][:len(finished)]
    client = Client()
    search = rag_document_search(mode='bm25', rerank=False)
    for case in packet:
        if case['record_id'] in seen:
            continue
        record = one_case(case, labels[case['record_id']], prior[case['record_id']], client, search)
        with output.open('a') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
        finished.append(record)
        print(f'{len(finished)}/80 frozen cases completed: {case["record_id"]}', flush=True)
    verify_lock()
    write(OUT / 'behavior.json', {
        'cases': 80, 'comparison': 'Historical prior frozen-locked integrated snapshot.',
        'preserved': {key: sum(r['preserved'][key] for r in finished) for key in finished[0]['preserved']},
        'routes_before': dict(Counter(r['snapshots']['baseline']['route'] for r in finished)),
        'routes_after': dict(Counter(r['snapshots']['integrated']['route'] for r in finished)),
        'pending_before': sum(r['snapshots']['baseline']['pending_reply'] is not None for r in finished),
        'pending_after': sum(r['snapshots']['integrated']['pending_reply'] is not None for r in finished),
        'changes': [{'record_id': r['record_id'], 'changes': {
            key: {'before': r['snapshots']['baseline'][key], 'after': r['snapshots']['integrated'][key]}
            for key, same in r['preserved'].items() if not same}}
            for r in finished if not all(r['preserved'].values())],
        'old_reopened_cases': sum('baseline' in r['reopened'] for r in finished),
        'current_reopened_cases': sum('integrated' in r['reopened'] for r in finished),
        'paired_reopened_cases': sum(set(r['reopened']) == {'baseline', 'integrated'} for r in finished),
        'paired_reopened_unchanged': sum(r['reply_preserved'] is True for r in finished),
        'followups': [{'record_id': r['record_id'], 'followup': r['followup'], 'reply_changes': r['reply_changes']}
                     for r in finished if r['followup']],
        'schema_valid': sum(not r['schema_errors'] for r in finished), 'endpoint_calls': 0, 'captured_model_replies': client.cache_hits,
        'holdout_cases': 0, 'code_and_gold_verified_after_run': True})
    print('All 80 frozen cases completed; code and GT integrity verified.', flush=True)


if __name__ == '__main__':
    main()
