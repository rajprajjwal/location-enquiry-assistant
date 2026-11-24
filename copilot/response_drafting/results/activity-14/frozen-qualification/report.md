# Activity 14 frozen evaluation

The validated implementation was locked and run on the same ordered 80 frozen inputs. The question-F1 target of 0.80 is not met. No application changes, label changes, threshold changes or case exclusions were made during the scored run.

| Measure | Prior saved frozen run | Locked rerun |
| --- | ---: | ---: |
| Clarifying-question F1 | 0.0000 | 0.1322 |
| Whole gold questions matched | 0/75 | 8/75 |
| Fact coverage | 4/99 (4.04%) | 18/99 (18.18%) |
| Questions produced | 13 | 46 |
| Questions on cases with empty gold lists | 8 | 24 |

This uses the original 75 frozen question groups and the same prior 99-atom decomposition. It does not use the separate 55-question working reference. Judgements compare actual question text with the frozen meaning and granularity: whole matches are one-to-one, independently bundled decisions cannot match several shorter gold questions, and partial facts are counted separately. All 80 judgements were cross-checked by another assistant with no disagreements, and bound to the exact prediction and gold hashes. This is assistant-reviewed evidence, not an independent human spot-check.

## Coverage gaps

Of 40 cases with gold questions, 27 generated no question. Their selection statuses were 17 `no_qualification_required`, eight `no_follow_up` and two preserved decline routes. The frozen questions were retained for scoring even when the customer had supplied a fact or declined more questions.

The system also generated 24 questions across 16 cases whose frozen gold lists are empty. Eight whole questions and 18 facts were matched. Only four additional gold groups have all their facts covered without an equivalent whole-question match, so the low score is primarily a coverage/selection gap, with a smaller grouping contribution. Missing distinctions include account versus backend/deployment ownership, billing and eligibility choices, and typical/maximum matrix sizes, frequency and concurrency. Related field names were not treated as equivalent automatically.

Sixteen facts are newly covered and two previously covered facts remain covered. The monthly/required-volume facts in AC-231 and DM-226 that were previously covered are now missed. Full unmatched questions and facts are in `per-case-question-analysis.json`. No fixes were made from these frozen results.

## Routes and pending replies

| Case | Route change | Pending reply change |
| --- | --- | --- |
| GT-LBS-AC-229 | clarification_needed → final | region → none |
| GT-LBS-AC-231 | clarification_needed → final | monthly_volume → none |
| GT-LBS-DIR-221 | escalated → final | none → none |
| GT-LBS-DM-226 | clarification_needed → final | monthly_volume → none |
| GT-LBS-RG-225 | clarification_needed → final | monthly_volume → none |

The four clarification changes deliver checklist advice without opening a generic customer intake question. DIR-221 now passes the document relevance review; that observation comes from a fresh model execution and is not isolated proof of a particular code change.

- Final-draft status: 61 → 66; escalated: 15 → 14; clarification-needed: four → zero.
- Initial routes are unchanged in 75/80 cases. Pending replies are unchanged in 76/80 and cleared in the four listed cases.
- Assigned owner and team are unchanged in 80/80. The full ownership object differs once because DIR-221 no longer includes its prior failed-review explanation.
- Approvals and proposed actions are unchanged in 80/80.
- No current reply turns were executed because no initial result leaves an active pending reply. The historical run reopened four pending cases, so this rerun does not claim four paired reopen-preservation checks.

## Execution and integrity

All 80 outputs are schema-valid. The run made 239 fresh completion calls with no recorded model-call errors, using the same institute model and BM25 mode; no seeded output cache was used. The implementation matches the working-eval version that passed 559 automated tests and four subtests. Source, configuration, schema, prompt, tokenizer and processed-corpus assets were copied and hashed before predictions. An isolated-runtime SQLite schema packaging omission was corrected before any model request; the application source was unchanged.

Post-run checks confirmed unchanged frozen input bytes, frozen GT export, original question text, prior fact labels, local GT workbook, alignment plan and all locked runtime assets. Every selected record is an eval record marked frozen-core. Holdout cases were neither selected nor scored.

The comparison column uses the prior saved `frozen-locked` results. Current completion calls are fresh, so observed behavior changes can include model-execution variation. The 1.000 working score does not transfer to this frozen reference. Activity 14 cannot be marked complete from this run.

## Saved evidence

- `implementation-lock.json`, `run-manifest.json`, `runtime/`: locked code, assets and selection lineage.
- `inputs.jsonl`, `ground-truth-frozen.csv`, `frozen-questions.json`, `locked-gold.json`: unchanged inputs and references.
- `predictions.jsonl`, `model-calls.jsonl`: full output/state records and model requests/responses.
- `scores.json`, `question-review.bound.json`, `per-case-question-analysis.json`: reproducible scores and exact judgements.
- `behavior.json`, `execution-quality.json`, `integrity-verification.json`: observed control changes and integrity checks.
- `fact-alignment-plan.json`, primary review files and independent audit files: evaluation-only semantic review provenance.

From the repository root, reproduce the saved scores without a model call:

```sh
PYTHONPATH=. .venv/bin/python -B copilot/response_drafting/results/activity-14/frozen-qualification/rescore.py
```


The full saved-response workflow replay uses the preserved runtime and historical baseline, requires no credentials and refuses uncaptured model requests:

```sh
PYTHONPATH=. .venv/bin/python -B copilot/response_drafting/results/activity-14/frozen-qualification/verification/replay_saved.py
```

It writes to `verification-output/`. Model-request lookup normalizes JSON object-key order while preserving array order and values, and binds each response to its frozen record and turn. This replay verifies reproducibility; it is not another live model evaluation. The frozen run above used fresh endpoint requests.
