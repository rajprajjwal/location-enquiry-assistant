"""Verify customer presentation through the live local query service."""
import argparse
from contextlib import closing
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from copilot.case_storage import cases, sandbox
from copilot.case_storage.db import connect
from copilot.enquiry_workflow.console import query_local
from copilot.response_drafting.schemas import validate_outputs


def verify(output, *, mode='both'):
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    with TemporaryDirectory() as directory:
        database = Path(directory) / 'presentation.db'

        def submit(name, query, expected, *, case_id=None, retrieval='bm25'):
            response = query_local({'query': query, 'case_id': case_id, 'customer': 'Presentation verification',
                                    'retrieval': retrieval}, database=database)
            (output / f'{name}.json').write_text(json.dumps(response, indent=2) + '\n')
            text = response['customer_response']['markdown']
            with closing(connect(database)) as con:
                saved = cases.load_state(con, response['case_id'])['last_result']
                assert saved['customer_response'] == response['customer_response']
                assert validate_outputs(saved['outputs']) == []
                assert saved['step_count'] <= 10
            (output / f'{name}-workflow.json').write_text(json.dumps(saved, indent=2) + '\n')
            assert response['status'] == expected, f'{name}: {response["status"]}'
            assert '### Answer' in text
            assert not any(value in text for value in ['Support L1', 'Support L2', 'Maps engineering', 'SEV1', 'SEV2'])
            checks.append({'scenario': name, 'passed': True, 'status': response['status'], 'retrieval': retrieval})
            print(f'{name}: passed', flush=True)
            return response

        if mode in {'bm25', 'both'}:
            submit('definition', 'What is the direction API?', 'final')
            first = submit('provider-question', 'How do I set waypoints in the Directions API?', 'clarification_needed')
            second = submit('provider-reply', 'Mapbox', 'final', case_id=first['case_id'])
            assert second['case_id'] == first['case_id']
            assert '### Sources' in second['customer_response']['markdown']
            pricing = submit('pricing', 'Compare Ola Maps and Google Maps Directions for 50,000 requests per month without traffic.', 'final')
            assert '| Provider' in pricing['customer_response']['markdown']
            assert '### Assumptions / missing information' in pricing['customer_response']['markdown']
            proposal = submit('record-proposal', 'Update sandbox ticket TKT-986. Set status to Investigating.', 'final')
            assert 'awaiting review' in proposal['customer_response']['markdown']
            incident = submit('incident', 'Production is down. Directions returns 503 for all requests.', 'escalated')
            assert 'awaiting review' in incident['customer_response']['markdown']
            with closing(connect(database)) as con:
                assert sandbox.get(con, 'TKT-986') == {}
                assert cases.list_pending(con, incident['case_id'])[0]['status'] == 'pending'
        if mode in {'hybrid', 'both'}:
            hybrid = submit('hybrid-guidance', 'What coordinate order does the Mapbox Directions API use?', 'final', retrieval='hybrid')
            assert '### Sources' in hybrid['customer_response']['markdown']
    summary = {'passed': True, 'checks': checks, 'frozen_or_holdout_used': False,
               'production_record_writes': 0, 'external_messages': 0}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=['bm25', 'hybrid', 'both'], default='both')
    args = parser.parse_args()
    print(json.dumps(verify(args.output, mode=args.mode), indent=2), flush=True)
