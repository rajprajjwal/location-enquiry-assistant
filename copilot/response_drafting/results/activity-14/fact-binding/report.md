# Supplied requirements and provider replies

The local project now extracts clear customer requirements before model planning and recognises a provider reply when a case is reopened. It preserves customer evidence and prevents daily outlet totals or published provider limits from becoming route-size requirements.

## Working-eval results

Both variants used the same 36 qualification cases and 28 groups. The original questions and GT workbook were unchanged. A separate assistant-reviewed working reference was locked before the comparison: 55 questions and 73 facts, with 12 record-level removals, corrections or wording changes. This is a semantic reference revision, not independent human acceptance. DM-228 removes a documentation-derived billing-basis question without silently adding workload or retention questions.

| Reference | Before F1 | After F1 | Before fact coverage | After fact coverage |
| --- | ---: | ---: | ---: | ---: |
| Original questions | 0.8852 | 0.8852 | 73/84 (86.90%) | 72/84 (85.71%) |
| Separate reviewed working reference | 0.9464 | 0.9821 | 72/73 (98.63%) | 73/73 (100.00%) |

The final version matches all 55 reviewed questions and covers 73/73 reviewed facts, while producing two additional initial questions. Original-label F1 remains unchanged because those labels still expect questions about supplied requirements and documentation-derived billing choices. Correctly suppressing such questions can reduce original-label fact coverage; this is reported rather than hidden.

- Targeted supplied/unknown checks improved from 8/13 to 13/13 across 11 working cases. This is a targeted check, not general extraction accuracy.
- Repeated supplied-fact groups in the targeted set: 2 before, 0 after. The saved JSON lists the exact fields and questions.
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

The locked live comparison made 147 endpoint calls with 0 endpoint errors. It exposed overlong explanatory reasons in DIR-047 and RG-230, which discarded valid groups. That original run remains saved at the top level.

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


The saved-response workflow replay needs no endpoint credentials and refuses uncaptured requests. Run it from the repository root:

```sh
PYTHONPATH=. .venv/bin/python -B copilot/response_drafting/results/activity-14/fact-binding/verification/replay_saved.py
```

It verifies the current Python source hashes and writes to `verification-output/`. The full Python snapshots preserve implementation evidence; execution manifests retain the original source paths. Historical execution scripts are retained separately from the portable replay and scorers.
