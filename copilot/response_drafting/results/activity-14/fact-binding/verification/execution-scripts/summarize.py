"""Summarize working-only binding fixes and preserve development-score provenance."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/fact-binding-working'
REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    final = OUT / 'final'
    manifest = load(final / 'run-manifest.json')
    scores = load(final / 'scores.json')
    behavior = load(final / 'behavior.json')
    live = load(OUT / 'behavior.json')
    rows = [json.loads(line) for line in (final / 'predictions.jsonl').read_text().splitlines()]
    assert len(rows) == len({r['record_id'] for r in rows}) == 36
    assert all(value == 36 for value in behavior['preserved'].values())
    assert behavior['endpoint_calls'] == 0
    assert all(digest(REPO / p) == h for p, h in manifest['code_hashes'].items())
    assert digest(REPO / 'data/ground-truth.xlsx') == manifest['workbook_sha256']
    assert digest(final / 'locked-gold.json') == manifest['original_gold_sha256']
    assert digest(final / 'reviewed-reference.json') == manifest['reviewed_reference_sha256']
    facts = load(OUT / 'targeted-fact-checks.json')
    expected = {}
    for check in facts['checks']:
        if check['method'] == 'integrated' and check['expected'] is not None:
            expected.setdefault(check['record_id'], set()).add(check['field'])
    repeated = {method: [] for method in ['baseline', 'integrated']}
    for row in rows:
        for method in repeated:
            groups = (row['details'][method]['selection'] or {}).get('groups', [])
            for group in groups:
                overlap = set(group['fields']) & expected.get(row['record_id'], set())
                if overlap:
                    repeated[method].append({'record_id': row['record_id'], 'fields': sorted(overlap), 'question': group['text']})
    review = load(final / 'reviewed-reference/question-review.bound.json')
    by_id = {r['record_id']: r for r in rows}
    extras = []
    for case in review['cases']:
        matched = {pair[0] for pair in case['methods']['integrated']['whole']}
        for index, text in enumerate(by_id[case['record_id']]['questions']['integrated'], 1):
            if index not in matched:
                extras.append({'record_id': case['record_id'], 'question': text})
    validation = {method: dict(Counter((audit or {}).get('status', 'no_qualification_audit')
                   for row in rows for audit in row['validation'][method].values()))
                  for method in ['baseline', 'integrated']}
    summary = {'scope': '36 working-eval qualification cases, 28 groups; no frozen or holdout cases.',
        'original_gt_workbook_unchanged': True, 'original_questions_unchanged': True,
        'reference_status': 'Separate assistant-reviewed development reference, locked before live comparison. Not independent human acceptance.',
        'scores': scores, 'targeted_fact_checks': facts['summary'],
        'targeted_repeated_supplied_facts': repeated, 'extra_questions': extras,
        'validation': validation, 'behavior': behavior,
        'live_calls': live['endpoint_calls'], 'live_endpoint_errors': live['endpoint_errors'],
        'tests': {'passed': 521, 'subtests_passed': 4, 'result': '521 passed, 4 subtests passed in 7.24s',
            'command': 'env PYTHONPATH=. .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/enquiry_workflow tests/enquiry_interpretation tests/model_gateway tests/test_comparison_pricing.py'},
        'pending': ['Two initial questions remain outside the reviewed reference: DM-228 region and RG-227 provider.',
                    'RG-227 provider reply clears the loop, but downstream drafting escalates after selecting four valid passage IDs where only three are permitted. Candidate evidence also lacks one requested provider. No draft-success claim.',
                    'Frozen acceptance has not been rerun.']}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
    original = scores['original-reference']; reviewed = scores['reviewed-reference']
    report = f'''# Supplied requirements and provider replies

The local project now extracts clear customer requirements before model planning and recognises a provider reply when a case is reopened. It preserves customer evidence and prevents daily outlet totals or published provider limits from becoming route-size requirements.

## Working-eval results

Both variants used the same 36 qualification cases and 28 groups. The original questions and GT workbook were unchanged. A separate assistant-reviewed working reference was locked before the comparison: 55 questions and 73 facts, with 12 record-level removals, corrections or wording changes. This is a semantic reference revision, not independent human acceptance. DM-228 removes a documentation-derived billing-basis question without silently adding workload or retention questions.

| Reference | Before F1 | After F1 | Before fact coverage | After fact coverage |
| --- | ---: | ---: | ---: | ---: |
| Original questions | {original['baseline']['f1']:.4f} | {original['integrated']['f1']:.4f} | {original['baseline']['facts']}/84 ({original['baseline']['fact_recall']:.2%}) | {original['integrated']['facts']}/84 ({original['integrated']['fact_recall']:.2%}) |
| Separate reviewed working reference | {reviewed['baseline']['f1']:.4f} | {reviewed['integrated']['f1']:.4f} | {reviewed['baseline']['facts']}/73 ({reviewed['baseline']['fact_recall']:.2%}) | {reviewed['integrated']['facts']}/73 ({reviewed['integrated']['fact_recall']:.2%}) |

The final version matches all 55 reviewed questions and covers 73/73 reviewed facts, while producing two additional initial questions. Original-label F1 remains unchanged because those labels still expect questions about supplied requirements and documentation-derived billing choices. Correctly suppressing such questions can reduce original-label fact coverage; this is reported rather than hidden.

- Targeted supplied/unknown checks improved from 8/13 to 13/13 across 11 working cases. This is a targeted check, not general extraction accuracy.
- Repeated supplied-fact groups in the targeted set: {len(repeated['baseline'])} before, {len(repeated['integrated'])} after. The saved JSON lists the exact fields and questions.
- All 11 initial workflow checks stayed unchanged for 36/36 cases, including route, owner, next action, approvals and pending reply.
- Three reopened cases stayed unchanged. RG-227 now accepts Mapbox and clears the provider pending state; it no longer repeats the provider question. It then reaches a separate drafting failure described below.
- 521 automated tests and four subtests passed, covering provenance, polarity, uncertainty, hypothetical questions, documentation claims, stale facts, provider aliases, ownership, case isolation and validation limits.

## Changes

- `copilot/qualification/extraction.py` extracts explicit requirements with exact spans. Assertions keep their own polarity and conditional scope. Rooftop-only precision and address components no longer depend on optional model proposals. Stop counts require route/request binding; provider capabilities do not establish customer needs.
- `copilot/qualification/facts.py` merges those facts before planning, invalidates old unbound stop counts and checks model excerpts against their enclosing customer assertion. Unsupported facts remain unknown.
- `copilot/pricing_tools/qualification.py` reuses explicit workload and app/API usage geography without equating it with billing country, company location or server location.
- `copilot/enquiry_workflow/cases.py`, `providers.py` and `workflow.py` bind a recognised answer to active `provider`/`current_provider` questions into validated interpretation and saved state. An initial multi-provider enquiry is not resolved using an arbitrary name from its text or history.
- `copilot/qualification/validation.py` caps only an overlong explanatory `reason`, revalidates the whole plan and records original/capped lengths and response hashes. Facts and groups remain intact, truncated completions remain rejected, and the shared one-model-repair limit remains in place.

## Evaluation provenance

The locked live comparison made {live['endpoint_calls']} endpoint calls with {len(live['endpoint_errors'])} endpoint errors. It exposed overlong explanatory reasons in DIR-047 and RG-230, which discarded valid groups. That original run remains saved at the top level.

After the reason cap, the same 36 paired workflows were replayed using captured live responses. Qualification completions were bound by record, method, turn and original response hash; other completions required exact request-cache hits. The final replay made zero endpoint calls and rejected cache misses. Its results are in `final/`. Both before/after binding variants share the reason correction, so the final table measures the binding changes with the same validation behavior. No frozen or holdout cases were used.

## Remaining work

Two initial questions remain outside the reviewed reference: the operating-region question in DM-228 and provider question in RG-227. They were preserved with the existing initial routes. Their policy requires separate review. The DIR-049 score covers route stop count; it does not independently prove that request-bundling requirements were captured.

The RG-227 reply clears the provider loop but does not yet produce a successful draft. The model selected passage IDs `[2, 4, 5, 6]`, all valid, when at most three are permitted. The saved error incorrectly describes this as an out-of-range ID. The candidate list also lacks Nominatim evidence for the original four-provider request. A safe next change is bounded selection repair and explicit handling of incomplete provider evidence, while retaining grounding and relevance checks. Do not arbitrarily trim the selection or accept unsupported citations.

The scoped binding fixes are verified on working-eval. Activity 14 acceptance remains open; no frozen rerun was performed.

## Saved files

- `final/scores.json`: final scores against both references.
- `final/predictions.jsonl`, `final/behavior.json`: paired questions, shared state and reopening outcomes.
- `final/original-reference/` and `final/reviewed-reference/`: bound alignments and offline scorers.
- `reference-changes.json`, `reviewed-reference.json`: separate prelocked reference changes; no workbook edits.
- `targeted-fact-checks.json`: exact supplied/unknown decisions and evidence.
- `plan-responses.jsonl`, `completion-cache/`: original live completions.
- `final/captured-response-binding.jsonl`: qualification replay bindings.

From the repository root, recompute the saved question scores with:

```sh
PYTHONPATH=. .venv/bin/python -B copilot/response_drafting/results/activity-14/fact-binding/final/reviewed-reference/rescore.py
PYTHONPATH=. .venv/bin/python -B copilot/response_drafting/results/activity-14/fact-binding/final/original-reference/rescore.py
```
'''
    (OUT / 'report.md').write_text(report)
    print(json.dumps({'scores': scores, 'repeated_groups': {k: len(v) for k, v in repeated.items()}, 'extras': extras}, indent=2))


if __name__ == '__main__':
    main()
