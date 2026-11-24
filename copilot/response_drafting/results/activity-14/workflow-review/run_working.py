"""Capture real working-eval workflows with exact-request caching and no label input."""
import argparse
from contextlib import closing
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--api-key-file', type=Path, required=True)
    parser.add_argument('--ca-cert', type=Path, required=True)
    parser.add_argument('--limit', type=int)
    options = parser.parse_args()
    sys.path.insert(0, str(options.runtime))
    os.environ.pop('TRACKB_GT_CSV', None)
    from copilot.model_gateway.client import LLMClient, Completion
    from copilot.enquiry_workflow.cases import run_case
    from copilot.enquiry_workflow.retrieval import rag_document_search
    from copilot.response_drafting.schemas import validate_outputs
    from copilot.case_storage import cases
    from copilot.case_storage.db import connect

    options.output.mkdir(parents=True, exist_ok=True)
    options.cache.mkdir(parents=True, exist_ok=True)
    inputs = json.loads(options.inputs.read_text())
    if isinstance(inputs, dict):
        inputs = inputs['cases']
    if options.limit:
        inputs = inputs[:options.limit]
    manifest = {'inputs_sha256': digest(options.inputs), 'records': len(inputs),
                'runtime': str(options.runtime), 'code_sha256': {
                    str(p.relative_to(options.runtime)): digest(p)
                    for p in (options.runtime / 'copilot').rglob('*.py') if 'results' not in p.parts},
                'retrieval': 'bm25', 'frozen_records': 0, 'holdout_records': 0,
                'reference_access': 'No reference labels are supplied to this runner or the model.'}
    path = options.output / 'run-manifest.json'
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise RuntimeError('Runtime or inputs changed; use a new output directory.')
    write(path, manifest)
    endpoint = LLMClient(api_key=options.api_key_file.read_text().strip(), ca_cert=str(options.ca_cert), timeout=30)

    class Client:
        record_id = None
        calls = cached_calls = 0

        def complete(self, messages, **kwargs):
            identity = sha256(json.dumps([messages, kwargs], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            location = options.cache / (identity + '.json')
            started = time.perf_counter()
            error = None
            try:
                if location.exists():
                    value = json.loads(location.read_text())
                    self.cached_calls += 1
                    response = Completion(**value)
                    cached = True
                else:
                    self.calls += 1
                    response = endpoint.complete(messages, **kwargs)
                    write(location, asdict(response))
                    cached = False
                return response
            except Exception as exc:
                error = type(exc).__name__
                raise
            finally:
                with (options.output / 'model-calls.jsonl').open('a') as stream:
                    stream.write(json.dumps({'record_id': self.record_id, 'request_sha256': identity,
                        'cached': location.exists() and not error and locals().get('cached', False),
                        'error_type': error, 'wall_ms': round((time.perf_counter()-started)*1000),
                        'response': asdict(response) if not error else None}) + '\n')

    def snapshot(con, result):
        output = result['outputs']
        memory = result['conversation_state']
        state = cases.load_state(con, result['case_id'])
        return {'route': result['status'], 'next_action': output['next_action'],
                'owner': output['responsible_role'], 'proposed_actions': result['proposed_actions'],
                'approvals': [{key: item[key] for key in ('type','payload','status')}
                              for item in cases.list_pending(con,result['case_id'])],
                'active_questions': result['clarifying_questions'], 'pending_reply': state.get('pending_clarification'),
                'asked': memory['questions_asked'], 'answered': memory['questions_answered'],
                'awaiting': [item for item in memory['unresolved_issues'] if item.startswith('Awaiting ')]}

    destination = options.output / 'predictions.jsonl'
    finished = [json.loads(line) for line in destination.read_text().splitlines()] if destination.exists() else []
    seen = {row['record_id'] for row in finished}
    assert len(seen) == len(finished) and seen <= {row['record_id'] for row in inputs}
    client, search = Client(), rag_document_search(mode='bm25', rerank=False)
    with closing(connect(options.output / 'cases.db')) as con:
        for row in inputs:
            if row['record_id'] in seen:
                continue
            client.record_id = row['record_id']
            cid = cases.create_case(con)
            for turn in row.get('history', []):
                cases.add_message(con, cid, turn['role'], turn['text'])
            started = time.perf_counter()
            result = run_case(con, row['query'], case_id=cid, client=client, search=search, diagnostic_planning=True)
            prediction = {'record_id': row['record_id'], 'group': row['group'], 'fold': row['fold'],
                'query': row['query'], 'history': row.get('history', []),
                'questions': [item['text'] for item in result['outputs']['clarifying_questions']['questions']],
                'snapshot': snapshot(con,result), 'schema_errors': validate_outputs(result['outputs']),
                'wall_ms': round((time.perf_counter()-started)*1000), 'result': result}
            finished.append(prediction)
            with destination.open('a') as stream:
                stream.write(json.dumps(prediction, ensure_ascii=False) + '\n')
            print(f"{len(finished)}/{len(inputs)} {row['record_id']} {result['status']} {len(prediction['questions'])} questions", flush=True)
    write(options.output/'execution.json', {'records':len(finished),'live_calls':client.calls,
        'cached_calls':client.cached_calls,'schema_valid':sum(not row['schema_errors'] for row in finished)})


if __name__ == '__main__':
    main()
