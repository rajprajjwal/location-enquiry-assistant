# Clarification routing and passage selection

The two extra working-eval questions and the passage-selection contract failure are fixed in the local project. Requested checklists now return advice without generic intake, and explicit documentation requests retrieve each named provider separately.

## Results on the same 36 working-eval cases

| Reference | F1 before | F1 after | Fact coverage before | Fact coverage after |
| --- | ---: | ---: | ---: | ---: |
| Original GT questions | 0.8852 | 0.9000 | 72/84 (85.71%) | 72/84 (85.71%) |
| Existing reviewed working reference | 0.9821 | 1.0000 | 73/73 (100.00%) | 73/73 (100.00%) |

The existing reviewed reference has 55 questions and 73 facts. Its content was unchanged. It is assistant-reviewed development evidence, not independent human acceptance. Both variants used the same reference for comparison. The original GT workbook and original questions were unchanged; frozen and holdout cases were excluded.

After the fix, the system produces 55 questions matching all 55 reviewed question groups. The extra region question in DM-228 and single-provider question in RG-227 are removed. Original-label scores remain lower because original questions still request supplied requirements or documentation-derived billing choices identified in the earlier review.

## Route and pending-reply changes

| Case | Initial route | Pending reply |
| --- | --- | --- |
| GT-LBS-AC-233 | clarification_needed → final | region → cleared |
| GT-LBS-DM-228 | clarification_needed → final | region → cleared |
| GT-LBS-RG-227 | clarification_needed → final | provider → cleared |
| GT-LBS-RG-228 | clarification_needed → final | monthly_volume → cleared |

The same policy also corrects two other explicit checklist requests, so four initial routes change rather than only the two cases with extra questions. The other 32 initial routes are unchanged. All 36 assigned-owner, approval and proposed-action checks are unchanged.

All four cases were also reopened from their old pending state using the new code. Each finished with a passing critic and no pending reply. Clearing a formerly unnecessary pending question is intentional; it is not a failed preservation check. The detailed history and state changes are in `behavior.json`.

## Implementation and verification

- `copilot/qualification/checklist.py` renders applicable missing customer decisions as advice, reusing supplied facts. References are exact excerpts, separated from the advice. It creates no stored pending reply or model calls. The workflow validates the schema and recomputes the deterministic draft before accepting it.
- `copilot/enquiry_workflow/routing.py` scopes documentation providers to the explicit request clause, excluding incidental historical mentions. The workflow queries two to four named documentation providers separately; combined price-comparison limits remain unchanged. The four-provider working case now returns a verified draft with nine citations and no missing-evidence note.
- `copilot/enquiry_workflow/passage_selection.py` distinguishes selection-count, type, range, JSON and truncation errors. It allows one repair against unchanged candidates within shared retry, token and deadline limits. It never trims or clamps selections, and grounding and relevance checks remain active.
- A controlled working-evidence smoke test injected the observed `[2, 4, 5, 6]` selection into six real retrieved candidates. One live model repair returned a valid selection within the three-passage limit, with exact retrieved citations. This verifies protocol recovery, not independent answer quality; the complete provider answer was checked separately.
- 559 automated tests and four subtests passed, including old pending-case reopening, ordinary intake, missing provider evidence, mixed requests, grounding and repair-budget bounds.

The paired evaluation reused exact-request cached completions and made 22 new unique workflow requests, plus one controlled repair request. No endpoint errors occurred. A temporary evaluation-runner case-ID error was corrected before the remaining legacy checks; completed cases and recorded responses were retained. No scored application outcome was discarded.

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


The saved full workflow replay requires no endpoint credentials and refuses uncaptured requests:

```sh
PYTHONPATH=. .venv/bin/python -B copilot/response_drafting/results/activity-14/clarification-routing/verification/replay_saved.py
```

It verifies current Python-source hashes, binds qualification completions by record, method, turn and captured response hash, and requires exact request-cache hits for other model calls. It writes to `verification-output/`. Source snapshots preserve the implementation and required baseline response schema; original execution manifests retain their recorded paths. Historical execution scripts are separate from the portable replay.
