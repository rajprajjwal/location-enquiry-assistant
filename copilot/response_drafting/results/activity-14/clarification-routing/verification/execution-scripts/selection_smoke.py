"""Verify live bounded repair of the observed selection-count failure on working evidence."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/clarification-routing-working'
manifest = json.loads((OUT / 'run-manifest.json').read_text())
sys.path.insert(0, manifest['runtime'])
from copilot.enquiry_workflow.answers import provider_query
from copilot.enquiry_workflow.retrieval import rag_document_search
from copilot.enquiry_workflow.workflow import _draft, _review
from copilot.model_gateway.client import Completion, LLMClient
from copilot.model_gateway.reliability import query_session, step_scope


class ControlledClient:
    def __init__(self):
        keys = ROOT / 'work/activity2'
        self.endpoint = LLMClient(api_key=(keys / 'trackb-api-key').read_text().strip(),
                                  ca_cert=str(keys / 'vm07-ca.crt'), timeout=30)
        self.requests = []

    def complete(self, messages, **options):
        payload = json.loads(messages[-1]['content'])
        injected = not payload.get('selection_repair')
        if injected:
            answer = Completion(text='{"passages":[2,4,5,6]}', raw='{"passages":[2,4,5,6]}',
                                model='captured-working-error-shape', usage={}, latency_ms=0,
                                think_seen=False, finish_reason='stop')
        else:
            answer = self.endpoint.complete(messages, **options)
        self.requests.append({'injected': injected, 'request': payload, 'response': asdict(answer)})
        return answer


def main():
    packet = json.loads((OUT / 'review-cases.json').read_text())
    case = next(r for r in packet if r['record_id'] == 'GT-LBS-RG-227')
    query = provider_query(case['query'], 'OSM Nominatim')
    passages = rag_document_search(mode='bm25', rerank=False).search(query, max_results=6)
    assert len(passages) == 6
    client = ControlledClient()
    with query_session() as session, step_scope('working_selection_repair'):
        draft, issue, retry_query = _draft(client, query, passages, None)
        events = session.events[:]
        retries = session.retries.copy()
    assert len(client.requests) == 2 and sum(not r['injected'] for r in client.requests) == 1
    assert client.requests[0]['request']['passages'] == client.requests[1]['request']['passages']
    assert issue is None, issue
    assert draft and len(draft['citations']) <= 3 and _review(draft, passages) is None
    value = {'scope': 'Controlled working-eval smoke: inject the observed four-selection shape into six real retrieved candidates, then use one live model repair. This is not a naturally recurring failure or answer-quality score.',
        'record_id': case['record_id'], 'provider_query': query,
        'candidate_count': len(passages), 'candidate_sha256': sha256(json.dumps(passages, sort_keys=True).encode()).hexdigest(),
        'injected_selections': [2, 4, 5, 6], 'endpoint_requests': 1,
        'valid_after_repair': True, 'grounding_review': 'passed',
        'retries': retries, 'events': events, 'requests': client.requests,
        'draft': draft, 'retry_query': retry_query}
    (OUT / 'selection-repair-smoke.json').write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'valid_after_repair': True, 'citations': len(draft['citations']), 'endpoint_requests': 1, 'retries': retries}))


if __name__ == '__main__':
    main()
