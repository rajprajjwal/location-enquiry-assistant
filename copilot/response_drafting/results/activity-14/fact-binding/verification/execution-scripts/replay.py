"""Compare qualification bindings in paired working-case workflows and reopened replies."""
from contextlib import closing, ExitStack
from dataclasses import asdict
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/fact-binding-working'
MANIFEST = json.loads((OUT / 'run-manifest.json').read_text())
sys.path.insert(0, MANIFEST['runtime'])
from copilot.case_storage import cases
from copilot.case_storage.db import connect
from copilot.enquiry_workflow import cases as current
from copilot.qualification import planning
from copilot.pricing_tools import qualification as pricing
from copilot.diagnostics import extraction as diagnostic_extraction
from copilot.response_drafting.schemas import validate_outputs


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


before = Path(MANIFEST['baseline_runtime']) / 'copilot'
old_facts = load('copilot.qualification._binding_before_facts', before / 'qualification/facts.py')
old_prices = load('copilot.pricing_tools._binding_before_prices', before / 'pricing_tools/qualification.py')
old_workflow = load('copilot.enquiry_workflow._binding_before_workflow', before / 'enquiry_workflow/workflow.py')
old_cases = load('copilot.enquiry_workflow._binding_before_cases', before / 'enquiry_workflow/cases.py')
old_cases.run_enquiry = old_workflow.run_enquiry
common = load('binding_common', ROOT / 'work/activity-14-questions/evaluate.py')
replies = {'provider': 'Mapbox', 'current_provider': 'Mapbox', 'region': 'Germany',
           'monthly_volume': '500,000 requests per month', 'timeline': 'June', 'api': 'Directions'}


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


class Client(common.Client):
    def __init__(self):
        super().__init__()
        self.record_id = self.method = None
        self.disk = OUT / 'completion-cache'
        self.disk.mkdir(exist_ok=True)

    def complete(self, *args, **kwargs):
        key = sha256(json.dumps([args, kwargs], sort_keys=True).encode()).hexdigest()
        path = self.disk / (key + '.json')
        if path.exists():
            from copilot.model_gateway.client import Completion
            self.cached_calls += 1
            result = Completion(**json.loads(path.read_text()))
        else:
            result = super().complete(*args, **kwargs)
            path.write_text(json.dumps(asdict(result), ensure_ascii=False) + '\n')
        messages = args[0] if args else kwargs.get('messages', [])
        try:
            payload = json.loads(messages[-1]['content'])
        except (ValueError, KeyError, IndexError):
            payload = {}
        if payload.get('qualification_plan') or payload.get('qualification_plan_repair'):
            with (OUT / 'plan-responses.jsonl').open('a') as stream:
                stream.write(json.dumps({'record_id': self.record_id, 'method': self.method,
                                         'repair_request': bool(payload.get('qualification_plan_repair')),
                                         'response': result.text, 'finish_reason': result.finish_reason}) + '\n')
        return result


def run(method, con, query, **kwargs):
    if method == 'integrated':
        return current.run_case(con, query, **kwargs)
    with ExitStack() as stack:
        for target, name, value in [
            (planning, 'context_from_result', old_facts.context_from_result),
            (planning, 'merge_model_facts', old_facts.merge_model_facts),
            (pricing, 'explicit_geographies', old_prices.explicit_geographies),
            (diagnostic_extraction, 'explicit_geographies', old_prices.explicit_geographies),
        ]:
            stack.enter_context(patch.object(target, name, value))
        return old_cases.run_case(con, query, **kwargs)


def pair(case, label, client, search):
    snapshots, resumed, questions, details, validations = {}, {}, {}, {}, {}
    with TemporaryDirectory(prefix='fact-binding-working-') as temp:
        for method in ('baseline', 'integrated'):
            client.method = method
            database = Path(temp) / (method + '.db')
            with closing(connect(database)) as con:
                cid = cases.create_case(con)
                for turn in case['history']:
                    cases.add_message(con, cid, turn['role'], turn['text'])
                result = run(method, con, case['query'], case_id=cid, client=client, search=search, diagnostic_planning=True)
                assert not validate_outputs(result['outputs'])
                snapshots[method] = common.snapshot(con, result)
                questions[method] = [q['text'] for q in result['outputs']['clarifying_questions']['questions']]
                details[method] = {'status': result['status'], 'selection': result.get('follow_up_selection'),
                                   'diagnostic_context': result.get('diagnostic_context'),
                                   'restored_diagnostic_state': result['conversation_state'].get('diagnostic_state')}
                validations[method] = {'initial': result.get('qualification_plan_validation')}
                pending = snapshots[method]['pending_reply']
            if pending and pending['field'] in replies:
                with closing(connect(database)) as con:
                    result = run(method, con, replies[pending['field']], case_id=cid, client=client, search=search, diagnostic_planning=True)
                    assert not validate_outputs(result['outputs'])
                    resumed[method] = common.snapshot(con, result)
                    validations[method]['resumed'] = result.get('qualification_plan_validation')
    return {'record_id': case['record_id'], 'group': case['group'], 'fold': case['fold'],
            'query': case['query'], 'history': case['history'], 'gold': label['questions'],
            'questions': questions, 'snapshots': snapshots, 'details': details, 'validation': validations,
            'preserved': {k: v == snapshots['integrated'][k] for k, v in snapshots['baseline'].items()},
            'reopened': resumed, 'reply_preserved': resumed.get('baseline') == resumed.get('integrated') if resumed else None,
            'reply_changes': {k: {'before': v, 'after': resumed['integrated'][k]} for k, v in resumed.get('baseline', {}).items()
                              if v != resumed.get('integrated', {}).get(k)}}


def main():
    def digest(path):
        return sha256(path.read_bytes()).hexdigest()
    for location, hashes in [('runtime', 'code_hashes'), ('baseline_runtime', 'baseline_hashes')]:
        assert all(digest(Path(MANIFEST[location]) / p) == h for p, h in MANIFEST[hashes].items())
    assert digest(OUT / 'review-cases.json') == MANIFEST['cases_sha256']
    assert digest(OUT / 'locked-gold.json') == MANIFEST['original_gold_sha256']
    assert digest(OUT / 'reviewed-reference.json') == MANIFEST['reviewed_reference_sha256']
    packet = json.loads((OUT / 'review-cases.json').read_text())
    labels = {r['record_id']: r for r in json.loads((OUT / 'locked-gold.json').read_text())['cases']}
    assert len(packet) == len(labels) == 36
    path = OUT / 'predictions.jsonl'
    rows = common.rows(path)
    seen = {r['record_id'] for r in rows}
    assert len(seen) == len(rows) and seen <= labels.keys()
    client = Client()
    search = common.rag_document_search(mode='bm25', rerank=False)
    exclusions = []
    for case in packet:
        if case['record_id'] in seen:
            continue
        client.record_id = case['record_id']
        for attempt in range(3):
            start = len(client.errors)
            row = pair(case, labels[case['record_id']], client, search)
            if len(client.errors) == start:
                break
            exclusions.append({'record_id': case['record_id'], 'attempt': attempt + 1, 'errors': client.errors[start:]})
            print(f'Retrying {case["record_id"]} after endpoint errors', flush=True)
            time.sleep(15)
        else:
            raise RuntimeError(f'No clean pair for {case["record_id"]}')
        with path.open('a') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        rows.append(row)
        print(f'{len(rows)}/36 paired working cases checked', flush=True)
    write(OUT / 'behavior.json', {'cases': len(rows),
        'preserved': {k: sum(r['preserved'][k] for r in rows) for k in rows[0]['preserved']},
        'initial_changes': [r['record_id'] for r in rows if not all(r['preserved'].values())],
        'reopened_cases': sum(r['reply_preserved'] is not None for r in rows),
        'reopened_unchanged': sum(r['reply_preserved'] is True for r in rows),
        'reopened_changes': [{'record_id': r['record_id'], 'changes': r['reply_changes']} for r in rows if r['reply_changes']],
        'endpoint_calls': client.calls, 'endpoint_errors': client.errors, 'excluded_attempts': exclusions})


if __name__ == '__main__':
    main()
