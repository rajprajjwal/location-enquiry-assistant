"""Capture the four-provider working answer using only cached model responses."""
from contextlib import closing
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/clarification-routing-working'
manifest = json.loads((OUT / 'run-manifest.json').read_text())
sys.path.insert(0, manifest['runtime'])
from copilot.case_storage import cases
from copilot.case_storage.db import connect
from copilot.enquiry_workflow.cases import run_case
from copilot.enquiry_workflow.retrieval import rag_document_search
from copilot.model_gateway.client import Completion

spec = importlib.util.spec_from_file_location('capture_old_route', ROOT / 'work/clarification-routing/replay.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class CacheClient:
    def __init__(self):
        self.calls = 0

    def complete(self, *args, **kwargs):
        key = sha256(json.dumps([args, kwargs], sort_keys=True).encode()).hexdigest()
        path = OUT / 'completion-cache' / (key + '.json')
        if not path.is_file():
            raise RuntimeError('Uncaptured request refused: ' + key)
        self.calls += 1
        return Completion(**json.loads(path.read_text()))


def capture(result):
    return {key: result.get(key) for key in ['status', 'clarifying_questions', 'response_draft', 'outputs',
        'steps', 'critic', 'tool_calls', 'proposed_actions', 'reliability']}


def main():
    packet = json.loads((OUT / 'review-cases.json').read_text())
    case = next(r for r in packet if r['record_id'] == 'GT-LBS-RG-227')
    client = CacheClient()
    search = rag_document_search(mode='bm25', rerank=False)
    with TemporaryDirectory(prefix='working-doc-answer-') as temp:
        with closing(connect(Path(temp) / 'fresh.db')) as con:
            result = run_case(con, case['query'], client=client, search=search, diagnostic_planning=True)
            fresh = capture(result)
            assert result['status'] == 'final'
            assert cases.load_state(con, result['case_id'])['pending_clarification'] is None
        with closing(connect(Path(temp) / 'legacy.db')) as con:
            before = runner.run('baseline', con, case['query'], client=client, search=search, diagnostic_planning=True)
            assert cases.load_state(con, before['case_id'])['pending_clarification']['field'] == 'provider'
            cid = before['case_id']
        with closing(connect(Path(temp) / 'legacy.db')) as con:
            result = run_case(con, 'Mapbox', case_id=cid, client=client, search=search, diagnostic_planning=True)
            reopened = capture(result)
            assert result['status'] == 'final'
            assert cases.load_state(con, cid)['pending_clarification'] is None
    output = {'record_id': case['record_id'], 'query': case['query'],
              'scope': 'Cached-response evidence capture; zero new endpoint calls.',
              'cache_hits': client.calls, 'fresh': fresh, 'legacy_reopen': reopened}
    (OUT / 'documentation-answer.json').write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'status': fresh['status'], 'providers': fresh['outputs']['comparison']['providers'],
                      'citations': len(fresh['response_draft']['citations']),
                      'notes': fresh['outputs']['comparison']['notes'],
                      'legacy_status': reopened['status'], 'cache_hits': client.calls}))


if __name__ == '__main__':
    main()
