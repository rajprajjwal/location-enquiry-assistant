# Enquiry workflow review results

Activity 14 remains open. The full working-eval question F1 improved from **37.50% to 55.83%**, below the **80%** target. Fact coverage improved from **40.24% to 52.44%**. These are development results, not frozen acceptance results.

## Results

All trials use the same 317 working-eval cases, 254 groups, 128 reference questions and 164 decomposed facts. Original questions, case membership and the source workbook remain unchanged.

| Configuration | Question F1 | Fact coverage | Questions on empty-reference cases |
|---|---:|---:|---:|
| Baseline | 37.50% | 40.24% | 66 |
| Shared requirement plan | 46.44% | 48.78% | 67 |
| Shared incident evidence and precise wording | 49.82% | 53.05% | 67 |
| Provider, operation and supplied-fact corrections | **55.83%** | **52.44%** | **34** |

The final trial matched 67 complete questions against 112 predictions and 128 reference questions. Precision was 59.82% and recall 52.34%, with 86 of 164 required facts covered. A whole-question match requires every reference fact; equivalent paraphrases count. In AC-213, a geographic-filter group displaced the points-of-interest group and lost a coverage-question match. That regression remains in the results.

Final API accuracy is 307/317 (96.85%); intent accuracy is 252/317 (79.50%). All 317 final output envelopes pass schema validation. Interpretation figures include deterministic postchecks, rather than measuring raw model output alone.

## Changes verified

- Scope facts and history to the active customer task. Preserve provider alternatives, current use and requested estimate assumptions separately.
- Use a shared requirement plan for structured questions and checklist advice. Keep matrix dimensions, quantities, periods and traffic conditions distinct.
- Pass exact, bounded retrieved excerpts to planning, with provider diversity and source provenance. Retrieval indexes and ranking configuration were not changed in this review.
- Reuse validated incident evidence for credit restoration, incorrect autocomplete predictions and credential exposure. Avoid competing narrow incident definitions.
- Bind compact storage requirements, named session termination and requested travel modes. Conditional estimate inputs remain assumptions rather than confirmed usage.
- Restrict qualification to the named provider and billed operation. Avoid Google account questions for a Mapbox-only quote, keystroke conversion for declared request counts, and input-format questions for an already-counted monthly element price.
- Bind current customer-status replies before ownership review. The original enquiry still supplies the incident and retrieval context.

## Workflow controls and ownership integration

The primary question comparison holds ownership implementation fixed. Across all 317 cases, the final incident and precision changes preserve the first trial's routes, owners, next actions, active questions, pending replies and approval proposals exactly. See `final-control-verification.json`.

The earlier holistic changes are broader: against baseline there are eight route changes, six owner/severity/escalation identity changes, six removed formal handoff proposals, four changed sandbox update categories and one changed pending provider question. These are documented in `paired-control-audit-v1.json`, including interpretation changes, an actual endpoint failure and the corrected broad-provider question. Do not describe the entire review as producing zero workflow changes.

The local project also retains the completed ownership implementation. Its separate [combined integration report](../../../../enquiry_workflow/results/workflow-review/combined-status-integration/report.json) verifies that new/existing corrections affect the same turn, reopening and deletion replay preserve evidence, ambiguous replies remain unconfirmed, and production incidents retain pending human approval. A separate fresh five-case live smoke covers all four APIs on the combined production code: all five outputs are schema-valid, with no model-call errors and the credit-restoration handoff pending approval. See `combined-live-smoke/verification.json`. This is integration evidence; the earlier Activity 16 acceptance scores were not rerun here.

The final production suite passed **1,122 tests and 15 subtests**, with zero failures and one skipped freshness test (`no local snapshot`). Source hashes remained stable throughout that run. See `production-verification.json` and `tests-final.xml`.

## What remains

The final 34 questions on empty references include four clearly unnecessary questions, 23 defensible missing-fact requests and seven questions that need an unresolved-answer gate. Empty gold alone does not establish that every question is wrong.

The 61 unmatched reference questions include 23 clear conflicts with supplied facts or instructions to proceed, 12 materiality questions needing review, and 26 further coverage gaps. The primary score includes all of them. A narrow decision catalogue and mutually exclusive scenario branches still omit material facts or displace another valid decision. Published remedies also need to be distinguished from unresolved diagnostics.

Reference policy needs consistent versioning: the earlier 52-case diagnostic reference adds 10 question groups where original GT has none; the 36-case qualification reference has 55 groups versus 65 originally. Their earlier scores cannot be treated as equivalent to this 317-case original-GT score. `failure-analysis.json` and `final-failure-status.json` retain the individual assessments. They are assistant reviews, not independent human acceptance.

Next, resolve the remaining answer-materiality and multi-decision coverage gaps on working-eval, and reconcile reference policy through a separate reviewed version. Keep original results visible. Lock that configuration before another frozen run, rubric comparison and human spot-check. No frozen or holdout cases were run or selected for development in this review.

## Reproduce and inspect

From the repository root, either command verifies the source-prediction and reference hashes and reproduces the final score without model access:

```sh
python copilot/response_drafting/results/activity-14/workflow-review/rescore_final.py
```

```sh
python3 copilot/response_drafting/results/activity-14/workflow-review/rescore_final.py
```

`baseline/` and `candidate-v3/` contain full predictions, model-call logs and sandbox case stores. `candidate-v3-score.json` includes bucket and grouped-fold results. Source snapshots, bound semantic judgements, original references and exact-request completions are saved alongside them.

The live workflow used the institute model through the shared client, zero-shot, and the same BM25 search configuration. Unchanged requests reused exact saved completions; changed requests called the endpoint. This is a paired development comparison, not two independent fresh runs or a latency benchmark. All working groups had prior development exposure; fold results are retrospective robustness checks, not untouched cross-validation. The baseline preserves its native endpoint failure. One process-suspension interruption was rerun on the identical baseline and recorded separately in `infrastructure-interruptions.json`.
