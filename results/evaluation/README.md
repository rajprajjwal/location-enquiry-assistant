# Evaluation and dashboard results

## Final status

- **Activity 22:** the final paired campaign is complete: 80 frozen cases and 96 eligible holdout cases. All cases now have accepted answer-quality scores, including one explicitly approved citation-format adjudication. There are zero unresolved generation, judgement or retrieval errors; the failed automatic attempts remain in the audit trail.
- **Activity 23:** complete. Both final runs display all 29 metrics with bucket, API and team filters. Saved metric recomputation is exact with no endpoint calls.
- **Data integrity:** GT, locked implementation, configuration and all generated answers are unchanged. Only the AC-050 baseline scored record was replaced. Seven flagged holdout records remain excluded; holdout approval remains provisional and independent review completion is not claimed.

For **GT-LBS-AC-050**, the automatic judge and its repair returned an empty citation list for one predicted citation. The project owner approved the audited `[false]` adjudication because no source evidence verifies that citation. The five numerical scores and reasons from the saved retry were retained exactly; only the citation flag was adjudicated. Its accepted answer accuracy is **0%**. Both holdout arms now use **96/96 cases**: baseline **40.43%**, agent **60.80%**. This is a disclosed single-record adjudication, not a change to the locked evaluator. See [adjudication](verification/judge-recovery-AC-050/adjudication.json) and [failed retry](verification/judge-recovery-AC-050/retry-failure.json).

Frozen agent citation coverage remains **95.71% across 70 drafts**; citation precision remains **96.68%**. Holdout agent coverage remains **98.73% across 79 drafts** and precision **98.92%**. These citation metrics do not imply complete answers: automatic comparison completeness remains **34.04%** on frozen and **25.12%** on holdout.

One frozen agent generation has incomplete usage, so the cost mean uses 79/80 cases. For the recovered judgement, overhead includes only the original failed attempt because retry usage and latency were not retained. Institute endpoint access is free; the monetary figures are illustrative estimates.

The baseline and agent receive identical enquiries and history, with reference answers and expected labels kept separate from generation. Accuracy, grounding, comparison completeness and history use are judged automatically by the model. Qualification uses deterministic, strict field agreement. These are not independent human ratings.

Only completed runs appear in the metric tables below. The locked final campaign uses 80 frozen cases, followed by 96 provisionally approved holdout cases. Progress is saved in `progress.json`.

## Baseline selection

Four strategies were compared on ten grouped working-eval cases, one per bucket. All four strategies used the same complete qualification contract and the final scorer.

| Strategy | Automatic rubric accuracy | Scored cases | Errors |
|---|---:|---:|---:|
| zero_shot | 33.00% | 10/10 | 0 |
| few_shot | 38.00% | 10/10 | 0 |
| self_consistency | 38.50% | 10/10 | 0 |
| decomposition | 38.00% | 10/10 | 0 |

**self_consistency** was selected. The paired flow was then checked on ten separate working groups, with no overlap between selection and validation groups.

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

### frozen-paired

Cases: 80; paired cases: 80; generation/judge/retrieval errors: 0.

| Metric | Baseline | Agent | Baseline scored | Agent scored |
|---|---:|---:|---:|---:|
| Rubric answer accuracy (ratio) | 39.15% | 69.20% | 80/80 | 80/80 |
| Supported factual claims (ratio) | 14.71% | 71.75% | 80/80 | 80/80 |
| Drafts with verified citations (ratio) | 2.50% | 95.71% | 80/80 | 70/80 |
| Supported citations (ratio) | 3.57% | 96.68% | 66/80 | 70/80 |
| Comparison completeness (ratio) | 9.50% | 34.04% | 40/80 | 40/80 |
| Qualification completeness (strict fields) (ratio) | 47.92% | 90.69% | 80/80 | 80/80 |
| History use (ratio) | 0.00% | 88.00% | 5/80 | 5/80 |
| Owner correctness (ratio) | 26.25% | 90.00% | 80/80 | 80/80 |
| Next-action correctness (ratio) | 27.50% | 100.00% | 80/80 | 80/80 |
| Successful registered tool calls (ratio) | Not scored / N/A | 100.00% | 0/80 | 80/80 |
| Expected tool coverage (ratio) | Not scored / N/A | 98.12% | 0/80 | 80/80 |
| Prediction schema validity (ratio) | 100.00% | 100.00% | 80/80 | 80/80 |
| Nonempty drafts (ratio) | 100.00% | 87.50% | 80/80 | 80/80 |
| Verbatim span Recall@1 (ratio) | Not scored / N/A | 10.15% | 0/80 | 73/80 |
| Verbatim span Recall@5 (ratio) | Not scored / N/A | 21.87% | 0/80 | 73/80 |
| Verbatim span Recall@10 (ratio) | Not scored / N/A | 25.44% | 0/80 | 73/80 |
| Source URL Recall@1 (ratio) | Not scored / N/A | 24.67% | 0/80 | 80/80 |
| Source URL Recall@5 (ratio) | Not scored / N/A | 56.60% | 0/80 | 80/80 |
| Source URL Recall@10 (ratio) | Not scored / N/A | 69.98% | 0/80 | 80/80 |
| Verbatim span MRR (ratio) | Not scored / N/A | 28.75% | 0/80 | 73/80 |
| Generation latency (ms) | 27118.92 | 11632.63 | 80/80 | 80/80 |
| Estimated generation cost (INR) | 0.036018 | 0.045868 | 80/80 | 79/80 |
| Reported input tokens (tokens) | 1453.69 | 4329.89 | 80/80 | 79/80 |
| Reported output tokens (tokens) | 1188.99 | 271.84 | 80/80 | 79/80 |
| Reported embedding tokens (tokens) | 0.00 | 30.32 | 80/80 | 79/80 |
| Evaluation judge latency (ms) | 5716.43 | 6369.40 | 80/80 | 80/80 |
| Estimated evaluation judge cost (INR) | 0.015044 | 0.041217 | 80/80 | 80/80 |
| Independent retrieval probe latency (ms) | Not scored / N/A | 3888.87 | 0/80 | 80/80 |
| Estimated retrieval probe cost (INR) | Not scored / N/A | 0.000037 | 0/80 | 80/80 |

Saved metric reaggregation: **pass**, zero numerical change and zero endpoint calls.

### holdout-final

Cases: 96; paired cases: 96; unresolved generation/judge/retrieval errors: 0; approved citation adjudications: 1.

| Metric | Baseline | Agent | Baseline scored | Agent scored |
|---|---:|---:|---:|---:|
| Rubric answer accuracy (ratio) | 40.43% | 60.80% | 96/96 | 96/96 |
| Supported factual claims (ratio) | 15.61% | 66.08% | 96/96 | 96/96 |
| Drafts with verified citations (ratio) | 1.04% | 98.73% | 96/96 | 79/96 |
| Supported citations (ratio) | 1.27% | 98.92% | 71/96 | 79/96 |
| Comparison completeness (ratio) | 2.33% | 25.12% | 43/96 | 43/96 |
| Qualification completeness (strict fields) (ratio) | 37.04% | 91.32% | 96/96 | 96/96 |
| History use (ratio) | 13.64% | 84.55% | 11/96 | 11/96 |
| Owner correctness (ratio) | 33.33% | 73.96% | 96/96 | 96/96 |
| Next-action correctness (ratio) | 22.92% | 85.42% | 96/96 | 96/96 |
| Successful registered tool calls (ratio) | Not scored / N/A | 100.00% | 0/96 | 94/96 |
| Expected tool coverage (ratio) | Not scored / N/A | 86.70% | 0/96 | 94/96 |
| Prediction schema validity (ratio) | 100.00% | 100.00% | 96/96 | 96/96 |
| Nonempty drafts (ratio) | 100.00% | 82.29% | 96/96 | 96/96 |
| Verbatim span Recall@1 (ratio) | Not scored / N/A | 3.39% | 0/96 | 73/96 |
| Verbatim span Recall@5 (ratio) | Not scored / N/A | 9.36% | 0/96 | 73/96 |
| Verbatim span Recall@10 (ratio) | Not scored / N/A | 9.36% | 0/96 | 73/96 |
| Source URL Recall@1 (ratio) | Not scored / N/A | 33.99% | 0/96 | 96/96 |
| Source URL Recall@5 (ratio) | Not scored / N/A | 61.85% | 0/96 | 96/96 |
| Source URL Recall@10 (ratio) | Not scored / N/A | 67.64% | 0/96 | 96/96 |
| Verbatim span MRR (ratio) | Not scored / N/A | 19.41% | 0/96 | 73/96 |
| Generation latency (ms) | 26453.28 | 9429.75 | 96/96 | 96/96 |
| Estimated generation cost (INR) | 0.035129 | 0.053931 | 96/96 | 96/96 |
| Reported input tokens (tokens) | 1450.34 | 5325.62 | 96/96 | 96/96 |
| Reported output tokens (tokens) | 1143.38 | 202.36 | 96/96 | 96/96 |
| Reported embedding tokens (tokens) | 0.00 | 34.83 | 96/96 | 96/96 |
| Evaluation judge latency (ms) | 5363.77 | 6249.70 | 96/96 | 96/96 |
| Estimated evaluation judge cost (INR) | 0.014572 | 0.040293 | 95/96 | 96/96 |
| Independent retrieval probe latency (ms) | Not scored / N/A | 3532.06 | 0/96 | 96/96 |
| Estimated retrieval probe cost (INR) | Not scored / N/A | 0.000045 | 0/96 | 96/96 |

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

The working validation covers ten cases to check integration. It does not mean all 317 working cases were evaluated. To run the full working pool, use the same command without the sampling option.