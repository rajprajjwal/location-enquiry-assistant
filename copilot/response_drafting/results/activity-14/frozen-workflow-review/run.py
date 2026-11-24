"""Run the unchanged 80 frozen inputs through the locked, complete case workflow."""
import argparse
from collections import Counter
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from time import perf_counter


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--api-key-file', type=Path, required=True)
    parser.add_argument('--ca-cert', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    lock = json.loads((out / 'implementation-lock.json').read_text())
    runtime = Path(lock['runtime'])
    repo = out.parents[4]

    def verify():
        assert all(digest(runtime / name) == checksum for name, checksum in lock['source_hashes'].items())
        assert all(digest(out / name) == checksum for name, checksum in lock['data_sha256'].items())
        assert digest(repo / 'data/ground-truth.xlsx') == lock['workbook_before_sha256']

    verify()
    inputs = read_rows(out / 'inputs.jsonl')
    ids = [row['record_id'] for row in inputs]
    assert ids == lock['frozen_record_ids'] and len(set(ids)) == 80
    assert all(not row['known_facts'] for row in inputs)
    os.environ.pop('TRACKB_GT_CSV', None)
    sys.path.insert(0, str(runtime))
    import copilot
    from copilot.case_storage import cases
    from copilot.case_storage.db import connect
    from copilot.enquiry_workflow.cases import run_case
    from copilot.enquiry_workflow.retrieval import rag_document_search
    from copilot.model_gateway.client import LLMClient
    from copilot.response_drafting.schemas import validate_outputs

    assert Path(copilot.__file__).resolve().parent == runtime / 'copilot'
    endpoint = LLMClient(api_key=args.api_key_file.read_text().strip(), ca_cert=str(args.ca_cert), timeout=30)

    class Client:
        record_id = None

        def complete(self, messages, **kwargs):
            started = perf_counter()
            record = {'record_id': self.record_id, 'messages': messages, 'options': kwargs,
                      'request_sha256': sha256(json.dumps([messages, kwargs], sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                      'cached': False}
            try:
                answer = endpoint.complete(messages, **kwargs)
                record['response'] = asdict(answer)
                record['error_type'] = None
                return answer
            except Exception as exc:
                record.update(error_type=type(exc).__name__, status_code=getattr(exc, 'status_code', None))
                raise
            finally:
                record['wall_ms'] = round((perf_counter() - started) * 1000)
                with (out / 'model-calls.jsonl').open('a') as stream:
                    stream.write(json.dumps(record, ensure_ascii=False) + '\n')

    def snapshot(con, result):
        output, memory = result['outputs'], result['conversation_state']
        return {'route': result['status'], 'next_action': output['next_action'],
                'owner': output['responsible_role'], 'proposed_actions': result['proposed_actions'],
                'approvals': [{key: item[key] for key in ('type', 'payload', 'status')}
                              for item in cases.list_pending(con, result['case_id'])],
                'active_questions': result['clarifying_questions'],
                'pending_reply': cases.load_state(con, result['case_id']).get('pending_clarification'),
                'asked': memory['questions_asked'], 'answered': memory['questions_answered']}

    destination = out / 'predictions.jsonl'
    completed = read_rows(destination)
    assert [row['record_id'] for row in completed] == ids[:len(completed)]
    client = Client()
    search = rag_document_search(mode='bm25', rerank=False)
    write(out / 'run-manifest.json', {**lock, 'status': 'running',
          'started_at_utc': datetime.now(timezone.utc).isoformat(),
          'reference_access': 'References are hashed for integrity; only customer input and retrieved documentation enter model requests.'})
    with closing(connect(out / 'cases.db')) as con:
        for row in inputs[len(completed):]:
            client.record_id = row['record_id']
            cid = cases.create_case(con)
            for turn in row['history']:
                cases.add_message(con, cid, turn['role'], turn['text'])
            started = perf_counter()
            record = {key: row[key] for key in ('record_id', 'query', 'history', 'known_facts')}
            try:
                result = run_case(con, row['query'], case_id=cid, client=client, search=search, diagnostic_planning=True)
                record.update(questions={'updated': [q['text'] for q in result['outputs']['clarifying_questions']['questions']]},
                              result=result, snapshot=snapshot(con, result),
                              schema_errors=validate_outputs(result['outputs']), execution_error=None)
            except Exception as exc:
                # Failed cases remain in the cohort and receive no question-match credit.
                record.update(questions={'updated': []}, result=None, snapshot=None,
                              schema_errors=['Execution failed: ' + type(exc).__name__], execution_error=type(exc).__name__)
            record['wall_ms'] = round((perf_counter() - started) * 1000)
            with destination.open('a') as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + '\n')
            completed.append(record)
            status = record['result']['status'] if record['result'] else record['execution_error']
            print(f"{len(completed)}/80 {row['record_id']} {status} {len(record['questions']['updated'])} questions", flush=True)
    verify()
    assert len(completed) == 80
    calls = read_rows(out / 'model-calls.jsonl')
    summary = {'cases': 80, 'frozen_cases': 80, 'holdout_cases': 0,
               'schema_valid': sum(not row['schema_errors'] for row in completed),
               'execution_errors': sum(bool(row['execution_error']) for row in completed),
               'fresh_model_calls': len(calls), 'cached_model_calls': 0,
               'model_call_errors': sum(bool(call['error_type']) for call in calls),
               'returned_models': dict(Counter(call['response']['model'] for call in calls if call.get('response'))),
               'routes': dict(Counter(row['result']['status'] if row['result'] else 'error' for row in completed)),
               'predicted_questions': sum(len(row['questions']['updated']) for row in completed),
               'predictions_sha256': digest(destination), 'integrity_verified': True,
               'finished_at_utc': datetime.now(timezone.utc).isoformat()}
    write(out / 'execution.json', summary)
    write(out / 'integrity-verification.json', {'passed': True, 'runtime_and_references_unchanged': True,
          'workbook_sha256': digest(repo / 'data/ground-truth.xlsx'),
          'data_sha256': lock['data_sha256'], 'ordered_frozen_ids_verified': True, 'holdout_cases': 0})
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
