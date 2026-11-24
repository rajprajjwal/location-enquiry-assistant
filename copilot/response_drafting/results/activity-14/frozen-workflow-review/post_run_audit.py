"""Read-only integrity monitoring and historical initial-turn control comparison."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import argparse
import json
import re
import time

REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')
OUT = REPO / 'copilot/response_drafting/results/activity-14/frozen-workflow-review'
PRIOR = OUT.parent / 'frozen-qualification'
UUID = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', re.I)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def rows(path):
    data = path.read_text() if path.exists() else ''
    if data and not data.endswith('\n'):
        data = data.rsplit('\n', 1)[0] + '\n' if '\n' in data else ''
    return [json.loads(line) for line in data.splitlines() if line.strip()]


def normalize(value, key=''):
    if isinstance(value, dict):
        return {k: normalize(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(item, key) for item in value]
    if isinstance(value, str) and key in {'id','action_id','approval_id','case_id','trace_id','source_trace_id'} and UUID.fullmatch(value):
        return '<generated-id>'
    return value


def owner_identity(owner):
    return {k: v for k, v in (owner or {}).items() if k != 'reason'}


def next_action_control(action):
    result = {k: v for k, v in (action or {}).items() if k != 'description'}
    if isinstance(result.get('escalation'), dict):
        result['escalation'] = {k: v for k, v in result['escalation'].items() if k != 'summary'}
    return normalize(result)


def compare_controls(current, lock):
    previous = rows(PRIOR / 'predictions.jsonl')
    old = {row['record_id']: row for row in previous}
    assert len(previous) == len(old) == 80
    assert digest(PRIOR / 'predictions.jsonl') == lock['previous_frozen_predictions_sha256']
    changes = []
    counts = Counter()
    before_routes, after_routes = Counter(), Counter()
    for row in current:
        rid = row['record_id']
        prior = old[rid]
        before, after = prior['snapshots']['integrated'], row['snapshot']
        before_routes[before['route']] += 1
        after_routes[after['route'] if after else 'execution_error'] += 1
        if after is None:
            counts['execution_failure'] += 1
            changes.append({'record_id':rid,'execution_error':row['execution_error'],'prior_route':before['route']})
            continue
        common = sorted(before.keys() & after.keys())
        different = {key:{'before':normalize(before[key]),'after':normalize(after[key])}
                     for key in common if normalize(before[key]) != normalize(after[key])}
        flags = {
            'route': before['route'] != after['route'],
            'owner_identity': owner_identity(before['owner']) != owner_identity(after['owner']),
            'owner_reason_only': before['owner'] != after['owner'] and owner_identity(before['owner']) == owner_identity(after['owner']),
            'next_action_control': next_action_control(before['next_action']) != next_action_control(after['next_action']),
            'next_action_description_only': before['next_action'] != after['next_action'] and next_action_control(before['next_action']) == next_action_control(after['next_action']),
            'approval_payload_or_status': normalize(before['approvals']) != normalize(after['approvals']),
            'proposed_actions': normalize(before['proposed_actions']) != normalize(after['proposed_actions']),
            'active_question': before['active_questions'] != after['active_questions'],
            'pending_reply': before['pending_reply'] != after['pending_reply'],
            'asked': before['asked'] != after['asked'],
            'answered': before['answered'] != after['answered'],
        }
        for key, changed in flags.items():
            counts[key] += bool(changed)
        old_interpretation = (prior.get('current_result') or {}).get('diagnostic_context',{}).get('interpretation')
        new_interpretation = (row.get('result') or {}).get('diagnostic_context',{}).get('interpretation')
        interpretation_changed = old_interpretation != new_interpretation
        counts['interpretation'] += interpretation_changed
        counts['any_common_snapshot_field'] += bool(different)
        counts['meaningful_control'] += any(flags[k] for k in ['route','owner_identity','next_action_control','approval_payload_or_status','proposed_actions','active_question','pending_reply'])
        if different or interpretation_changed:
            changes.append({'record_id':rid,'changes':different,'changed_categories':flags,
                'interpretation':{'before':old_interpretation,'after':new_interpretation} if interpretation_changed else None})
    result = {
        'cases':len(current),'paired_cases':len(current),'prior_predictions_sha256':digest(PRIOR/'predictions.jsonl'),
        'current_predictions_sha256':digest(OUT/'predictions.jsonl'),
        'comparison':'Historical frozen-qualification initial snapshots.integrated versus current initial snapshot. No synthetic replies or reopened turns included.',
        'interpretation':'Observed differences across complete implementations and fresh model requests; this is not isolated attribution, new correctness scoring, tuning or a control-invariance claim.',
        'normalization':'Only UUID values in generated workflow identifier fields are normalized; customer facts, record targets and payload content remain visible.',
        'uncompared_prior_only_fields':['awaiting','clarification_messages'],
        'counts':dict(counts),'routes_before':dict(before_routes),'routes_after':dict(after_routes),'records':changes,
        'frozen_cases':80,'holdout_cases':0,
    }
    write('prior-frozen-control-comparison.json',result)
    return result


def audit(initial):
    lock = json.loads((OUT/'implementation-lock.json').read_text())
    runtime = Path(lock['runtime'])
    inputs = rows(OUT/'inputs.jsonl')
    ids = [row['record_id'] for row in inputs]
    records, calls = rows(OUT/'predictions.jsonl'), rows(OUT/'model-calls.jsonl')
    canonical = REPO/'eval/frozen-interpretation'
    checks = {
        'implementation_lock_unchanged': digest(OUT/'implementation-lock.json') == initial['lock_sha256'],
        'runner_unchanged': digest(OUT/'run.py') == initial['runner_sha256'],
        'runtime_source_hashes_match': all((runtime/p).is_file() and digest(runtime/p)==h for p,h in lock['source_hashes'].items()),
        'production_matches_locked_runtime': all((REPO/p).is_file() and digest(REPO/p)==h for p,h in lock['source_hashes'].items()),
        'locked_inputs_and_references_match': all(digest(OUT/p)==h for p,h in lock['data_sha256'].items()),
        'canonical_inputs_match': digest(canonical/'inputs.jsonl')==lock['data_sha256']['inputs.jsonl'],
        'canonical_manifest_match': digest(canonical/'manifest.json')==lock['data_sha256']['frozen-input-manifest.json'],
        'canonical_frozen_gt_match': digest(canonical/'ground-truth-frozen.csv')==lock['data_sha256']['ground-truth-frozen.csv'],
        'workbook_unchanged': digest(REPO/'data/ground-truth.xlsx')==lock['workbook_before_sha256'],
        'all_80_unique_original_input_ids': ids==lock['frozen_record_ids'] and len(ids)==len(set(ids))==80,
        'prediction_ids_are_ordered_frozen_prefix': [x['record_id'] for x in records]==ids[:len(records)],
        'prediction_input_binding': all({k:x[k] for k in ['record_id','query','history','known_facts']}==inputs[index] for index,x in enumerate(records)),
        'model_call_record_ids_from_frozen_only': all(c['record_id'] in ids for c in calls),
        'no_cached_completions': all(c.get('cached') is False for c in calls),
    }
    progress = {'at_utc':datetime.now(timezone.utc).isoformat(),'records':len(records),'calls':len(calls),
        'execution_errors':sum(bool(x.get('execution_error')) for x in records),
        'logical_model_errors':sum(bool(x.get('error_type')) for x in calls),
        'all_integrity_checks_passed':all(checks.values()),'failed_checks':[k for k,v in checks.items() if not v]}
    with (OUT/'audit-progress.jsonl').open('a') as stream:
        stream.write(json.dumps(progress)+'\n')
    write('runner-audit.json',{'scope':'Read-only monitor of the user-authorized run; no application/reference edits or model requests.',
        'runner_sha256':initial['runner_sha256'],'implementation_lock_sha256':initial['lock_sha256'],
        'checks':checks,'latest_progress':progress,'source_hashes_verified':len(lock['source_hashes']),
        'holdout_inputs':0,'note':'Fresh client calls are logical complete() calls; bounded transport attempts inside the model client are not individual rows in model-calls.jsonl.'})
    if not all(checks.values()):
        raise RuntimeError('Integrity audit failed: '+', '.join(progress['failed_checks']))
    if len(records)==80 and (OUT/'execution.json').exists():
        compare = compare_controls(records,lock)
        write('post-run-integrity-audit.json',{'passed':True,'checks':checks,'source_hashes_verified':len(lock['source_hashes']),
            'at_utc':progress['at_utc'],'cases':80,'holdout_cases':0,'schema_valid':sum(not x['schema_errors'] for x in records),
            'workbook_sha256':digest(REPO/'data/ground-truth.xlsx'),
            'predictions_sha256':digest(OUT/'predictions.jsonl'),'implementation_lock_sha256':initial['lock_sha256'],
            'runtime_model':'Qwen/Qwen3-8B','synthetic_reply_runs':0,'user_action_execution':0,
            'historical_control_comparison':'prior-frozen-control-comparison.json','control_difference_counts':compare['counts'],
            'qualification':'This verifies integrity and observed controls, not semantic question correctness or independent human acceptance.'})
        progress['complete']=True
    print(json.dumps(progress),flush=True)
    return progress


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--watch',action='store_true');args=parser.parse_args()
    initial={'lock_sha256':digest(OUT/'implementation-lock.json'),'runner_sha256':digest(OUT/'run.py')}
    while True:
        progress=audit(initial)
        if progress.get('complete') or not args.watch:
            return
        time.sleep(30)


if __name__=='__main__':
    main()
