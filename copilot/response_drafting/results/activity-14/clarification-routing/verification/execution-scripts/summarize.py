"""Report working question quality and intentional routing changes without label edits."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/clarification-routing-working'
REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    manifest = load(OUT / 'run-manifest.json')
    scores = load(OUT / 'scores.json')
    behavior = load(OUT / 'behavior.json')
    smoke = load(OUT / 'selection-repair-smoke.json')
    docs = load(OUT / 'documentation-answer.json')
    rows = [json.loads(line) for line in (OUT / 'predictions.jsonl').read_text().splitlines()]
    assert len(rows) == len({r['record_id'] for r in rows}) == 36
    assert digest(REPO / 'data/ground-truth.xlsx') == manifest['workbook_sha256']
    assert digest(OUT / 'locked-gold.json') == manifest['original_gold_sha256']
    assert digest(OUT / 'reviewed-reference.json') == manifest['reviewed_reference_sha256']
    assert all(digest(REPO / p) == h for p, h in manifest['code_hashes'].items())
    assert behavior['pending_before'] == 4 and behavior['pending_after'] == 0
    assert len(behavior['legacy_reopen_checks']) == 4
    assert all(c['outcome']['snapshot']['route'] == 'final' and c['outcome']['snapshot']['pending_reply'] is None
               and c['outcome']['critic']['verdict'] == 'pass' for c in behavior['legacy_reopen_checks'])
    assert all(behavior['preserved'][k] == 36 for k in ['owner', 'approvals', 'proposed_actions'])
    assert smoke['valid_after_repair'] and smoke['endpoint_requests'] == 1
    assert docs['fresh']['status'] == 'final' and docs['fresh']['outputs']['comparison']['notes'] is None
    original, reviewed = scores['original-reference'], scores['reviewed-reference']
    changes = [{'record_id': c['record_id'], 'route_before': c['changes']['route']['before'],
                'route_after': c['changes']['route']['after'],
                'pending_field_before': c['changes']['pending_reply']['before']['field'],
                'pending_after': c['changes']['pending_reply']['after']}
               for c in behavior['initial_changes']]
    summary = {'scope': 'Same 36 qualification working-eval cases; no frozen or holdout cases.',
        'original_gt_unchanged': True, 'prior_reviewed_reference_unchanged': True,
        'reviewed_reference_status': 'Existing assistant-reviewed development reference; not independent human acceptance.',
        'scores': scores, 'route_and_pending_changes': changes,
        'other_routes_unchanged': 32, 'assigned_owners_unchanged': 36, 'approvals_and_proposals_unchanged': 36,
        'old_pending_reopens_passed': 4, 'extra_questions_before': 2, 'extra_questions_after': 0,
        'documentation_answer': {'providers': docs['fresh']['outputs']['comparison']['providers'],
            'citations': len(docs['fresh']['response_draft']['citations']), 'missing_evidence_note': None},
        'selection_repair': {'controlled_injected_error': True, 'maximum_selections': 3,
            'endpoint_requests': 1, 'shared_retry_credits_used': 1, 'grounding_review': 'passed'},
        'tests': {'passed': 559, 'subtests_passed': 4, 'result': '559 passed, 4 subtests passed in 7.44s',
            'command': 'env PYTHONPATH=. .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/enquiry_workflow tests/enquiry_interpretation tests/model_gateway tests/test_comparison_pricing.py'},
        'model_execution': {'identical_request_cache_reused': True,
            'new_unique_workflow_completions': behavior['new_unique_completions'],
            'additional_controlled_smoke_requests': 1, 'endpoint_errors': behavior['endpoint_errors']}}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    table = '\n'.join(f"| {c['record_id']} | {c['route_before']} → {c['route_after']} | {c['pending_field_before']} → cleared |" for c in changes)
    report = f'''# Clarification routing and passage selection

The two extra working-eval questions and the passage-selection contract failure are fixed in the local project. Requested checklists now return advice without generic intake, and explicit documentation requests retrieve each named provider separately.

## Results on the same 36 working-eval cases

| Reference | F1 before | F1 after | Fact coverage before | Fact coverage after |
| --- | ---: | ---: | ---: | ---: |
| Original GT questions | {original['baseline']['f1']:.4f} | {original['integrated']['f1']:.4f} | {original['baseline']['facts']}/84 ({original['baseline']['fact_recall']:.2%}) | {original['integrated']['facts']}/84 ({original['integrated']['fact_recall']:.2%}) |
| Existing reviewed working reference | {reviewed['baseline']['f1']:.4f} | {reviewed['integrated']['f1']:.4f} | {reviewed['baseline']['facts']}/73 ({reviewed['baseline']['fact_recall']:.2%}) | {reviewed['integrated']['facts']}/73 ({reviewed['integrated']['fact_recall']:.2%}) |

The existing reviewed reference has 55 questions and 73 facts. Its content was unchanged. It is assistant-reviewed development evidence, not independent human acceptance. Both variants used the same reference for comparison. The original GT workbook and original questions were unchanged; frozen and holdout cases were excluded.

After the fix, the system produces 55 questions matching all 55 reviewed question groups. The extra region question in DM-228 and single-provider question in RG-227 are removed. Original-label scores remain lower because original questions still request supplied requirements or documentation-derived billing choices identified in the earlier review.

## Route and pending-reply changes

| Case | Initial route | Pending reply |
| --- | --- | --- |
{table}

The same policy also corrects two other explicit checklist requests, so four initial routes change rather than only the two cases with extra questions. The other 32 initial routes are unchanged. All 36 assigned-owner, approval and proposed-action checks are unchanged.

All four cases were also reopened from their old pending state using the new code. Each finished with a passing critic and no pending reply. Clearing a formerly unnecessary pending question is intentional; it is not a failed preservation check. The detailed history and state changes are in `behavior.json`.

## Implementation and verification

- `copilot/qualification/checklist.py` renders applicable missing customer decisions as advice, reusing supplied facts. References are exact excerpts, separated from the advice. It creates no stored pending reply or model calls. The workflow validates the schema and recomputes the deterministic draft before accepting it.
- `copilot/enquiry_workflow/routing.py` scopes documentation providers to the explicit request clause, excluding incidental historical mentions. The workflow queries two to four named documentation providers separately; combined price-comparison limits remain unchanged. The four-provider working case now returns a verified draft with nine citations and no missing-evidence note.
- `copilot/enquiry_workflow/passage_selection.py` distinguishes selection-count, type, range, JSON and truncation errors. It allows one repair against unchanged candidates within shared retry, token and deadline limits. It never trims or clamps selections, and grounding and relevance checks remain active.
- A controlled working-evidence smoke test injected the observed `[2, 4, 5, 6]` selection into six real retrieved candidates. One live model repair returned a valid selection within the three-passage limit, with exact retrieved citations. This verifies protocol recovery, not independent answer quality; the complete provider answer was checked separately.
- 559 automated tests and four subtests passed, including old pending-case reopening, ordinary intake, missing provider evidence, mixed requests, grounding and repair-budget bounds.

The paired evaluation reused exact-request cached completions and made {behavior['new_unique_completions']} new unique workflow requests, plus one controlled repair request. No endpoint errors occurred. A temporary evaluation-runner case-ID error was corrected before the remaining legacy checks; completed cases and recorded responses were retained. No scored application outcome was discarded.

## Saved evidence

- `scores.json`: before/after metrics for both unchanged references.
- `predictions.jsonl`, `behavior.json`: questions, initial routes and old pending-case reopenings.
- `documentation-answer.json`: full four-provider draft, citations, comparison and critic results for a fresh case and legacy reopening.
- `selection-repair-smoke.json`: unchanged candidates, invalid selection, live repair, citations and retry audit.
- `original-reference/`, `reviewed-reference/`: exact outputs, labels, hash-bound alignments and offline scorers.
- `run-manifest.json`, `source-snapshot/`: code and input lineage.

From the repository root, rescore the saved outputs without a model call:

```sh
PYTHONPATH=. .venv/bin/python -B copilot/response_drafting/results/activity-14/clarification-routing/reviewed-reference/rescore.py
PYTHONPATH=. .venv/bin/python -B copilot/response_drafting/results/activity-14/clarification-routing/original-reference/rescore.py
```

These scoped fixes are verified on working-eval. No frozen acceptance claim is made.
'''
    (OUT / 'report.md').write_text(report)
    print(json.dumps({'scores': scores, 'changes': changes, 'tests_passed': 559}, indent=2))


if __name__ == '__main__':
    main()
