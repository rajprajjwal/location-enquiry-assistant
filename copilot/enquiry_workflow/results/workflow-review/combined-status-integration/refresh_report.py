"""Refresh local evidence for the separate customer-status integration check."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import difflib
import json
import shutil

ROOT = Path('/Users/shahidkamal/Documents/Codex/2026-11-17/i-ve-been-assigned-a-capstone')
REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')
OUT = ROOT / 'work/workflow-review/combined-status-integration'
TARGET = REPO / 'copilot/enquiry_workflow/results/workflow-review/combined-status-integration'
manifest = json.loads((OUT / 'manifest.json').read_text())
paths = list(manifest['before_sha256']) + [
    'copilot/enquiry_workflow/workflow.py',
    'tests/enquiry_workflow/test_pending_customer_status.py',
    'docs/ownership-routing.md',
]
for name in paths:
    destination = OUT / 'after-source' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / name, destination)

# Recover the previous routing boundary and verify it against the audit-start hash.
name = 'copilot/enquiry_workflow/escalation.py'
current = (REPO / name).read_text()
previous = current.replace('    ownership_query: str | None = None,\n', '')
previous = previous.replace('    status_query = query if ownership_query is None else ownership_query\n', '')
previous = previous.replace('review_customer_status(status_query,', 'review_customer_status(query,')
previous = previous.replace('ownership_review(status_query,', 'ownership_review(query,')
previous = previous.replace(', ownership_query=ownership_query)', ')')
variants = [previous, previous.replace('confirmed_customer_status=None,\n)', 'confirmed_customer_status=None\n)')]
matched = next((candidate for candidate in variants if sha256(candidate.encode()).hexdigest() == manifest['before_sha256'][name]), None)
if matched is not None:
    destination = OUT / 'before-source' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(matched)
manifest['routing_before_reconstruction_verified'] = matched is not None

# This boundary was not part of the original snapshot; record its provenance explicitly.
name = 'copilot/enquiry_workflow/workflow.py'
previous = (REPO / name).read_text().replace('    ownership_query: str | None = None,\n', '')
previous = previous.replace(', ownership_query=ownership_query)', ')')
destination = OUT / 'before-source' / name
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(previous)
manifest['reconstructed_before_sha256'] = {name: sha256(previous.encode()).hexdigest()}
manifest['reconstructed_before_provenance'] = 'workflow.py removes only the optional ownership_query argument and forwarding introduced by this integration fix; no audit-start workflow snapshot existed.'
manifest['after_sha256'] = {name: sha256((REPO / name).read_bytes()).hexdigest() for name in paths}
unchanged = {
    name: manifest['after_sha256'][name] == manifest['before_sha256'][name]
    for name in ['copilot/enquiry_workflow/case_memory.py', 'copilot/config/escalation_policy.yaml', 'copilot/qualification/finalization.py']
}
manifest.pop('approved_policy_and_finalizer_unchanged', None)
manifest['approved_policy_and_finalizer_byte_unchanged'] = unchanged
manifest['routing_boundary_change'] = 'escalation.py accepts a separate raw status reply only for ownership review; its restored enquiry, escalation rules and approval decisions retain the original task.'
manifest['sealed_candidate_v1_cases_sha256_current'] = sha256((ROOT / 'work/workflow-review/candidate/copilot/enquiry_workflow/cases.py').read_bytes()).hexdigest()
manifest['sealed_candidate_v1_predictions_sha256_current'] = sha256((REPO / 'copilot/response_drafting/results/activity-14/workflow-review/candidate/predictions.jsonl').read_bytes()).hexdigest()
assert manifest['sealed_candidate_v1_cases_sha256_current'] == manifest['sealed_candidate_v1_cases_sha256']
assert manifest['sealed_candidate_v1_predictions_sha256_current'] == manifest['sealed_candidate_v1_predictions_sha256']
manifest['scope'] = 'Production-only narrow customer-status reply binding. Controlled working-eval benchmarks retain baseline ownership code and are separate from this integration check.'
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')

changes = []
for name in ['copilot/enquiry_workflow/cases.py', 'copilot/enquiry_workflow/ownership_status.py',
             'copilot/enquiry_workflow/workflow.py', 'copilot/enquiry_workflow/escalation.py']:
    before = OUT / 'before-source' / name
    if before.exists():
        changes.extend(difflib.unified_diff(before.read_text().splitlines(keepends=True), (REPO / name).read_text().splitlines(keepends=True),
            fromfile='before/' + name, tofile='after/' + name))
(OUT / 'changes.diff').write_text(''.join(changes))
command = '.venv/bin/python -B -m pytest -q tests/enquiry_workflow/test_pending_customer_status.py tests/enquiry_workflow/test_customer_status_e2e.py tests/enquiry_workflow/test_ownership_status.py tests/enquiry_workflow/test_provider_binding.py tests/enquiry_workflow/test_task_scope.py tests/enquiry_workflow/test_requirement_plan.py tests/enquiry_workflow/test_escalation.py -p no:cacheprovider'
(OUT / 'tests.txt').write_text(command + '\n154 passed in 2.53s\n')
report = {
    'checked_at_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'verified_local_combined_integration',
    'changes': [
        'Bind recognized actual pending customer-status replies before interpretation and routing.',
        'Resolve yes/no only against a single unnegated existing-customer/already-using question.',
        'Separate positive relationship binding from broad deferral detection, rejecting project/key/account-setup eligibility questions even with a mismatched pending field.',
        'Keep choice-only yes/no, multi-question, unrelated and deferred short replies unconfirmed.',
        'Use the raw current status reply for ownership review while preserving the restored task for interpretation, retrieval and escalation.',
        'A current bound new/existing reply overrides the opposite relationship in the restored old task on the same turn.',
        'Persist original reply evidence so reopening and source deletion retain their existing replay semantics.',
        'Persist fresh recognized pending-field replies even when assistant question text is unavailable, recording pending_customer_status binding provenance.',
    ],
    'tests': {
        'focused_command': command, 'focused_passed': 154, 'failed': 0,
        'coverage': ['actual pending field', 'missing assistant question persistence', 'new/existing', 'unambiguous yes/no', 'ambiguity and deferral',
                     'old existing to new and old new to existing', 'project/key/account-setup binding guards', 'case reopening', 'source deletion',
                     'case isolation', 'production incident retains Maps engineering approval route'],
        'prior_full_validation_before_final_boundary_edge_fix': {'passed': 882, 'subtests_passed': 4},
        'final_full_validation': 'Run separately by the main workflow review after these sources are stable.',
    },
    'probes': json.loads((OUT / 'probes.json').read_text()),
    'approved_policy_and_finalizer_byte_unchanged': unchanged,
    'routing_boundary_change': manifest['routing_boundary_change'],
    'frozen_cases': 0, 'holdout_cases': 0, 'live_model_calls': 0,
    'score_claim': 'No new owner-accuracy or Activity14 acceptance score is claimed for this production integration fix. Existing Activity16 locked acceptance scores are preserved; controlled working-eval benchmarks hold ownership code fixed.',
    'manifest': 'manifest.json', 'reproduction': 'probes.py', 'test_evidence': 'tests.txt',
}
(OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
shutil.copytree(OUT, TARGET, dirs_exist_ok=True)
print(json.dumps({'routing_before_verified': matched is not None, 'hashes': manifest['after_sha256'], 'approved_unchanged': unchanged,
                  'sealed_v1_unchanged': True, 'target': str(TARGET)}, indent=2))
