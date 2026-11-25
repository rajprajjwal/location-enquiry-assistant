# Evaluation and dashboard results

**Paused:** 24/80 frozen pairs are fully scored. The next baseline generation is cached; holdout is unstarted. Resume from `resume-checkpoint.json` without restarting selection or validation.

The harness compares the existing agent with a plain-model baseline using identical enquiries and history. References and expected labels are isolated from generation. Scores for accuracy, grounding, comparison completeness and history use are automatic model judgements; qualification uses deterministic strict field agreement, not independent human ratings.

Only completed runs appear in the metric tables below. The locked final campaign uses 80 frozen cases, followed by 96 provisionally approved holdout cases. Progress is saved in `progress.json`.

## Baseline selection

Four strategies were compared on ten grouped working-eval cases, one per bucket. All four strategies used the same complete qualification contract and the final scorer.

| Strategy | Automatic rubric accuracy | Scored cases | Errors |
|---|---:|---:|---:|
| zero_shot | 33.00% | 10/10 | 0 |
| few_shot | 38.00% | 10/10 | 0 |
| self_consistency | 38.50% | 10/10 | 0 |
| decomposition | 38.00% | 10/10 | 0 |

Selected strategy: **self_consistency**. Ten separate working groups validate the paired flow; selection groups do not appear in validation.

## Evaluation runs

### working-contract-validation

Cases: 10; paired cases: 10; generation/judge/retrieval errors: 0.

| Metric | Baseline | Agent | Baseline scored | Agent scored |
|---|---:|---:|---:|---:|
| Rubric answer accuracy (ratio) | 28.30% | 58.00% | 10/10 | 10/10 |
| Supported factual claims (ratio) | 10.00% | 65.50% | 10/10 | 10/10 |
| Drafts with verified citations (ratio) | 10.00% | 100.00% | 10/10 | 9/10 |
| Supported citations (ratio) | 10.00% | 100.00% | 8/10 | 9/10 |
| Comparison completeness (ratio) | 8.33% | 35.00% | 6/10 | 6/10 |
| Qualification completeness (strict fields) (ratio) | 38.89% | 86.67% | 10/10 | 10/10 |
| History use (ratio) | 0.00% | 100.00% | 1/10 | 1/10 |
| Owner correctness (ratio) | 40.00% | 90.00% | 10/10 | 10/10 |
| Next-action correctness (ratio) | 40.00% | 90.00% | 10/10 | 10/10 |
| Successful registered tool calls (ratio) | Not scored / N/A | 91.67% | 0/10 | 10/10 |
| Expected tool coverage (ratio) | Not scored / N/A | 80.00% | 0/10 | 10/10 |
| Prediction schema validity (ratio) | 100.00% | 100.00% | 10/10 | 10/10 |
| Nonempty drafts (ratio) | 100.00% | 90.00% | 10/10 | 10/10 |
| Verbatim span Recall@1 (ratio) | Not scored / N/A | 0.00% | 0/10 | 7/10 |
| Verbatim span Recall@5 (ratio) | Not scored / N/A | 11.22% | 0/10 | 7/10 |
| Verbatim span Recall@10 (ratio) | Not scored / N/A | 13.01% | 0/10 | 7/10 |
| Source URL Recall@1 (ratio) | Not scored / N/A | 32.50% | 0/10 | 10/10 |
| Source URL Recall@5 (ratio) | Not scored / N/A | 63.44% | 0/10 | 10/10 |
| Source URL Recall@10 (ratio) | Not scored / N/A | 67.67% | 0/10 | 10/10 |
| Verbatim span MRR (ratio) | Not scored / N/A | 19.29% | 0/10 | 7/10 |
| Generation latency (ms) | 27634.91 | 19452.47 | 10/10 | 10/10 |
| Estimated generation cost (INR) | 0.035434 | 0.052871 | 10/10 | 10/10 |
| Reported input tokens (tokens) | 1447.20 | 4958.90 | 10/10 | 10/10 |
| Reported output tokens (tokens) | 1161.20 | 330.80 | 10/10 | 10/10 |
| Reported embedding tokens (tokens) | 0.00 | 20.20 | 10/10 | 10/10 |
| Evaluation judge latency (ms) | 5826.19 | 7246.76 | 10/10 | 10/10 |
| Estimated evaluation judge cost (INR) | 0.016024 | 0.046540 | 10/10 | 10/10 |
| Independent retrieval probe latency (ms) | Not scored / N/A | 8271.71 | 0/10 | 10/10 |
| Estimated retrieval probe cost (INR) | Not scored / N/A | 0.000055 | 0/10 | 10/10 |

Saved metric reaggregation: **pass**, zero numerical change and zero endpoint calls.

## Holdout and data integrity

The project owner explicitly authorized provisional approval to proceed. This is recorded in `holdout-review.json`; independent review completion is not claimed and workbook review-status fields were not changed.
All 7 holdout members of previously flagged cross-split pairs are excluded conservatively, leaving 96 cases. Exact normalized text and template-family checks on the current workbook found zero remaining cross-split matches. The prior cosine screening is retained; a fresh cosine audit is not claimed.
The global holdout ledger permits one final run directory and an exact resume only. Frozen results and holdout results must not be used for prompt or retrieval tuning. Strict span metrics exclude summary labels and therefore differ from reviewed-summary retrieval scores from earlier component evaluations.

## Dashboard and verification

The read-only Streamlit dashboard displays all 29 harness metrics with bucket, API and team filters, case errors, units, scored denominators and downloadable run bindings. Completed runs are rediscovered every ten seconds without editing dashboard code. The server uses http://localhost:8503.
Automated suite: 1,157 tests and 15 subtests passed; one optional raw-snapshot freshness test skipped. The live hybrid smoke passed for both arms. Reference/empty calibration passed three working cases; fresh reference repeats had zero score difference. A separate fresh-judge repeat check on the real validation predictions is saved beside that run.
The automated judge uses the institute model. Actual institute endpoint access is free. Displayed INR costs are illustrative estimates at the configured token rates and ₹94/USD. Generation and judge/retrieval-probe overhead remain separate.

## Files and commands

- `baseline-contract-selection/selection.json`: candidate scores, selected method and disjoint validation groups.
- Each completed run: `manifest.json`, `cases.jsonl`, `records.jsonl`, `summary.json`, `repeatability.json`.
- `verification/`: test, calibration, leakage and dashboard evidence.
- `holdout-review.json`, `holdout-ledger.json`: approval basis, exclusions and final-run protection.
- [Harness guide](../../copilot/evaluation/README.md) and [dashboard guide](../../copilot/metrics_dashboard/README.md).

Working validation is a ten-case integration check, not a claim that all 317 working cases have been evaluated. The full working pool is supported by the same command without its sampling option.
