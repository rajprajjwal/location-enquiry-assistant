"""Measure fresh interpretation and routing without cached ownership decisions."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from copilot.enquiry_interpretation import interpret
from copilot.enquiry_workflow.escalation import route_enquiry
from copilot.enquiry_workflow.verification.verify_ownership import scores
from copilot.model_gateway.client import LLMClient
from copilot.model_gateway.reliability import query_session


def verify_live(inputs, output, *, client=None):
    """Retain failed cases in the denominator and never pass labels to the model."""
    if os.environ.get('TRACKB_GT_CSV'):
        raise ValueError('Unset TRACKB_GT_CSV for a label-free ownership run.')
    rows = [json.loads(line) for line in inputs.read_text().splitlines()]
    if not rows or len(rows) != len({r['record_id'] for r in rows}):
        raise ValueError('Expected distinct saved enquiry inputs.')
    output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    files = ['enquiry_workflow/escalation.py', 'enquiry_workflow/ownership_status.py',
             'enquiry_workflow/routine_triage.py', 'enquiry_workflow/billing_policy.py',
             'safety/customer_evidence.py', 'safety/escalation_policy.py',
             'config/escalation_policy.yaml', 'model_gateway/client.py']
    manifest = {'input_sha256': sha256(inputs.read_bytes()).hexdigest(), 'cases': len(rows),
                'mode': 'fresh interpretation and live routing; no cached decisions',
                'sources': {name: sha256((root/name).read_bytes()).hexdigest() for name in files}}
    manifest_file = output/'manifest.json'
    if manifest_file.exists() and json.loads(manifest_file.read_text()) != manifest:
        raise ValueError('Inputs or implementation changed; choose a new output directory.')
    manifest_file.write_text(json.dumps(manifest, indent=2)+'\n')
    destination = output/'predictions.jsonl'
    saved = [json.loads(line) for line in destination.read_text().splitlines()] if destination.exists() else []
    seen = {row['record_id'] for row in saved}
    if not seen <= {r['record_id'] for r in rows} or len(seen) != len(saved):
        raise ValueError('Saved records do not match the input cohort.')
    active_client = client or LLMClient()
    with destination.open('a') as stream:
        for row in rows:
            if row['record_id'] in seen:
                continue
            value = {k: row[k] for k in ['record_id', 'query', 'history', 'expected']}
            value['actual'] = {'owner': None, 'escalate': None, 'reason': None}
            value['error'] = None
            with query_session() as session:
                enquiry = {'query': row['query'], 'history': row['history'], 'known_facts': []}
                parsed = interpret(enquiry, client=active_client)
                value['interpretation'] = parsed.model_dump(mode='json')
                value['semantic_abstention'] = parsed.abstain and parsed.abstain_reason == 'no_rule_match'
                if parsed.abstain and not value['semantic_abstention']:
                    value['error'] = f'interpretation:{parsed.abstain_reason}'
                else:
                    route = route_enquiry(row['query'], parsed, history=row['history'], client=active_client)
                    if route['source'] == 'fallback':
                        value['error'] = 'handoff_classification_unavailable'
                    else:
                        value['actual'] = {'owner': route['owner'], 'escalate': route['should_escalate'],
                                           'reason': route['reason'], 'source': route['source'],
                                           'ownership_review': route['ownership_review']}
                value['reliability'] = session.snapshot()
            stream.write(json.dumps(value)+'\n'); stream.flush()
            saved.append(value); seen.add(row['record_id'])
            print(f'Fresh ownership {len(saved)}/{len(rows)}', flush=True)
    valid = [row for row in saved if row['error'] is None]
    # Valid-only diagnostics are separate from all-case target qualification.
    valid_metrics = scores(valid) if valid else None
    owner_correct = sum(row['actual']['owner'] == row['expected']['owner'] for row in valid)
    summary = {'cases': len(rows), 'completed': len(saved), 'valid_cases': len(valid),
               'errors': [{'record_id': r['record_id'], 'error': r['error']} for r in saved if r['error']],
               'semantic_abstentions': [r['record_id'] for r in saved if r.get('semantic_abstention')],
               'owner_correct': owner_correct, 'owner_accuracy_all_cases': owner_correct/len(rows),
               'valid_only_diagnostics': valid_metrics, 'complete_valid_run': len(valid) == len(rows),
               'mode': manifest['mode'], 'production_record_writes': 0, 'external_messages': 0}
    summary['passes'] = bool(summary['complete_valid_run'] and valid_metrics['owner_accuracy'] >= .9
        and valid_metrics['escalation_precision'] is not None and valid_metrics['escalation_precision'] >= .8
        and valid_metrics['escalation_recall'] is not None and valid_metrics['escalation_recall'] >= .9
        and valid_metrics['escalation_reason_coverage'] == 1)
    (output/'scores.json').write_text(json.dumps(summary, indent=2)+'\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    print(json.dumps(verify_live(options.inputs, options.output), indent=2))
