# Activity 3 — Two-annotator pilot agreement

Compared Update_A and Update_P from the supplied workbook. All ten cases P01–P10 are present exactly once in each sheet. Query, history, known facts and dataset membership match the original pilot packet. No missing labels or unmatched cases were excluded.

The agreed pilot measures intent, API and team separately, with a target of κ ≥ 0.70 for every field.

| Field | Exact agreement | Observed agreement | Chance agreement | Cohen’s κ | Target | Result |
|---|---:|---:|---:|---:|---:|---|
| intent | 8/10 | 80% | 13% | 0.7701 | ≥0.70 | Pass |
| api | 9/10 | 90% | 25% | 0.8667 | ≥0.70 | Pass |
| team | 10/10 | 100% | 52% | 1.0000 | ≥0.70 | Pass |

## Formatting only

The scoring exports use controlled-vocabulary casing and trim surrounding whitespace. Submitted workbook cells remain unchanged.

- Update_A!I2: `sales` → `Sales`.
- Update_P!G11: `pricing_quote ` → `pricing_quote`.

Without formatting normalization, team agreement is 9/10 and κ=0.8148. `sales` and `Sales` denote the same permitted team, so the normalized result is used.

## Label disagreements retained for adjudication

| Case | Field | Update_A | Update_P |
|---|---|---|---|
| P08 | intent | capability_match | sales_qualification |
| P10 | intent | pricing_comparison | pricing_quote |
| P10 | api | autocomplete | directions |

No semantic labels were changed or adjudicated. The reported κ uses the original independent decisions, after formatting-only normalization. Save any later consensus in adjudication.template.csv separately; do not replace the original submissions or recompute initial agreement on consensus labels.

## Scope and next step

The Activity 3 annotation-agreement criterion passes for all three required fields. Confirm the final labels for P08 and P10 in the separate adjudication file before promoting a consensus annotation. High agreement measures consistency between annotators; it does not establish factual correctness or complete gold-record validation.

Other review fields remain outside this agreement score. Update_A P01 has bucket `capability_question`, which is not an allowed bucket. The sheets also differ on the P09 and P10 buckets. Reference answers, citations, rubric, escalation and tool expectations still require their own completeness/evidence checks. Missing optional review fields were not counted as agreement.

## Reproduce

```bash
python eval/score_activity3_workbook.py --workbook /path/to/annotation-2-members.xlsx --output /path/to/new-results
python3 eval/score_activity3_workbook.py --workbook /path/to/annotation-2-members.xlsx --output /path/to/new-results
```

Use either command in the activated project environment. The output directory must be new. The exports can also be checked with the existing CSV scorer:

```bash
python eval/score_activity3_pilot.py eval/activity-3-pilot/results/annotation-agreement/Update_A.csv eval/activity-3-pilot/results/annotation-agreement/Update_P.csv
python3 eval/score_activity3_pilot.py eval/activity-3-pilot/results/annotation-agreement/Update_A.csv eval/activity-3-pilot/results/annotation-agreement/Update_P.csv
```

## Evidence

The source workbook is preserved byte-for-byte in annotations.source.xlsx. Update_A.csv and Update_P.csv contain only the four pilot scoring columns. scores.json includes marginals, chance agreement and confusion matrices. pair-comparison.csv records all 30 comparisons; disagreements.csv and adjudication.template.csv retain the unresolved decisions.

Source SHA-256: `cd9e134186b229b3ee8dfaca3a3ae60e12dc9540e34fb5ba164a8a960c35fbf9`. Frozen GT was not changed. No model, inference endpoint or holdout cases were used.
