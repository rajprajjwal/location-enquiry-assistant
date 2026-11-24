Shared qualification contract and planner — working-eval, 24 November 2026

The implementation is in copilot/qualification. It adds a versioned Pydantic qualification context and planner contract, normalized shared facts, applicable API decision profiles and multiple question groups. The model extracts evidenced customer facts and proposes priorities. The profile catalogue checks the complete set of applicable requirements. Questions are rendered after the workflow has selected its route.

Validated interpretation values, customer statements and history are merged into the existing diagnostic state. Exact excerpts, literal or controlled-alias grounding, Boolean polarity and field-type checks prevent unsupported supplied facts from suppressing questions. Explicit output languages and terminating Places SKUs are reused. The existing question filter now accepts trusted customer-requirement templates while retaining credential checks and its default documentation filtering.

The evaluation selected every qualification-bucket case from the fixed 317-case working-eval cohort: 36 cases in 28 groups, retaining the five existing folds. Only those IDs were processed for workbook labels. No frozen or holdout records were used for implementation or scoring in this work. Existing original working GT question text was locked before predictions and remains unchanged. Its 65 questions were decomposed into 84 atomic facts for separate coverage measurement.

| Metric on the same 36 cases | Before change | Final implementation |
| --- | ---: | ---: |
| Clarifying-question F1 | 0.000 | 0.840 |
| Whole questions matched | 0/65 | 50/65 |
| Fact coverage | 2/84 (2.38%) | 69/84 (82.14%) |
| Question precision | 0% | 92.59% |
| Question recall | 0% | 76.92% |
| Questions produced | 5 | 54 |
| Questions on the three empty-GT cases | 1 | 1 |

The 0.80 F1 development threshold is met under the saved assistant-reviewed fact alignment. These are development/regression results. Labels and question grouping were available during implementation, several development comparisons were run, and the score is not independent human acceptance or grouped cross-validation. The existing folds are recorded for future comparisons, not presented as unseen validation here. Whole-question and atomic-fact judgements are bound to the exact prediction and label hashes; the canonical fact alignment and actual question text are saved for review.

All 36 paired snapshots preserved route, owner, next action, approvals, proposed actions, active clarifications, pending reply and saved clarification history. Four real pending clarifications were answered and reopened: AC-233, DM-228, RG-227 and RG-228. Resumed behavior matched in all four. Reply turns are excluded from initial-turn question metrics. New questions are staff suggestions; they do not replace the active reply mechanism.

Targeted verification passed 336 tests and four subtests. The tests cover multi-group contracts, interpretation reuse, supplied and declined facts, explicit false values, unsupported omissions, field types, language versus modality, group completeness, active-question enrichment, endpoint output limits and the documentation-filter boundary. All app outputs in the paired replay passed schema checks. The final replay made 169 endpoint calls with no recorded transport errors or excluded attempts.

Two qualification-plan responses failed local validation and used the diagnostic fallback. One was the initial DM-030 enquiry; the other was a resumed monthly-volume reply. The fallback preserved the app output schema and workflow control state. These failures are retained in planner-execution.jsonl and execution-quality.json rather than selectively rerun for a better score.

Remaining gaps are separated from the headline score.

- The pre-prediction label audit flagged ten cases with eleven apparently supplied facts still requested by original GT. Examples include Place Details Essentials already named in AC-021 through AC-024, required address storage in RG-010 and RG-014, and Hindi output in RG-228. Primary scoring keeps these questions; the workbook and original labels were not corrected. Some intent and confirmation ambiguities still need independent review.
- DIR-049 exposes a genuine normalization gap. The interpretation output records 15–20 outlets as raw monthly_volume with no normalized monthly count or unit. The qualification normalizer currently treats that non-null object as supplied. A usable-monthly-volume check is needed before using it to suppress a workload question.
- DM-030 missed its input-representation question after the plan validation fallback. Logging detailed validation locations and testing constrained repair on working-eval are follow-up work.
- Some GT questions ask for decisions the system can resolve or compare from documentation, such as matrix billing units, or ask the customer to choose between scenarios they explicitly requested together. Those need a consistent working annotation policy before changing labels.
- RG-227 retains an existing active provider question despite the documentation enquiry naming multiple providers. It is the one output on an empty-GT case. This was already present in the baseline and remains because active routes and pending replies were held fixed.

The first full model-selected comparison scored F1 0.690 and fact coverage 61/84. Subsequent complete comparisons and partial integration checks are retained in subfolders and files. The final version incorporates grounded facts, complete decision grouping and the customer-requirement filter boundary. Original labels were unchanged across these comparisons.

The shared JSON Schemas are contracts/qualification/context.schema.json and plan.schema.json. The module README describes each file and the diagnostic_context.qualification interface. Existing interpretation input and output schemas remain compatible. Further qualification profiles and negative controls outside these 36 cases still require working-eval verification. This run does not establish performance on all 317 cases or complete Activity 14 frozen acceptance.

Source hashes, original label hashes and the workbook byte hash were verified unchanged after the final run. The live production code matches the evaluated snapshot. No GT workbook writes were performed.

Saved evidence includes predictions.jsonl, original-working-labels.json, locked-gold.json, question-review.bound.json, question-alignment.json, scores.json, behavior.json, remaining-gaps.json, planner-execution.jsonl, execution-quality.json, label-conflicts.json, integrity-verification.json and run-manifest.json. To reproduce the saved scores from the repository root:

```sh
PYTHONPATH=. .venv/bin/python -B copilot/response_drafting/results/activity-14/qualification-planner/rescore.py
```
