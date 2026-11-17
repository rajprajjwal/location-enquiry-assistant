# Activity 2 interpretation scoring

Cases scored: 80

Intent accuracy improved from 71/80 to 72/80. The intent gate requires 72/80. 5/5 numeric gates passed.

Evaluation mode: reviewed_workbook_frozen_core

**Offline rescore of the same saved predictions.** The approved AC-081 gold intent changed in this revision. Workbook-level sign-off is pending.

| Reference metric (frozen targets) | Actual | Minimum | Result |
|---|---:|---:|---|
| intent_acc | 0.9000 | 0.9000 | PASS |
| api_acc | 1.0000 | 0.9500 | PASS |
| qual_f1 | 0.9058 | 0.8500 | PASS |
| missing_recall | 0.9741 | 0.8500 | PASS |
| schema_valid_rate | 1.0000 | 1.0000 | PASS |

Abstain rate: 0.0000. Repair rate: 0.0000.
Team accuracy: 0.9125. Qualification F1 excluding `use_case_api`: 0.7759. Missing-field precision: 0.9850.

## By bucket

| Bucket | Cases | Intent accuracy | API accuracy | Team accuracy | Qualification F1 | Missing recall |
|---|---:|---:|---:|---:|---:|---:|
| capabilitycompare | 11 | 0.8182 | 1.0000 | 0.8182 | 0.9600 | 1.0000 |
| coveragecompare | 5 | 0.6000 | 1.0000 | 1.0000 | 0.7059 | 1.0000 |
| docs | 5 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| history | 5 | 1.0000 | 1.0000 | 1.0000 | 0.8462 | 1.0000 |
| interpretation | 5 | 0.8000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| limitscompare | 7 | 0.5714 | 1.0000 | 0.7143 | 0.9524 | 1.0000 |
| ownership | 11 | 1.0000 | 1.0000 | 0.9091 | 0.8947 | 0.9459 |
| pricecompare | 5 | 1.0000 | 1.0000 | 1.0000 | 0.9600 | 1.0000 |
| qualification | 15 | 1.0000 | 1.0000 | 0.8667 | 0.9000 | 0.9787 |
| updates | 11 | 1.0000 | 1.0000 | 1.0000 | 0.9048 | 0.8889 |

## By api

| Api | Cases | Intent accuracy | API accuracy | Team accuracy | Qualification F1 | Missing recall |
|---|---:|---:|---:|---:|---:|---:|
| autocomplete | 20 | 0.9000 | 1.0000 | 1.0000 | 0.9206 | 0.9437 |
| directions | 20 | 0.9000 | 1.0000 | 0.9000 | 0.8986 | 1.0000 |
| distance_matrix | 20 | 0.9000 | 1.0000 | 0.9500 | 0.9275 | 0.9853 |
| reverse_geocode | 20 | 0.9000 | 1.0000 | 0.8000 | 0.8800 | 0.9688 |

## By team

| Team | Cases | Intent accuracy | API accuracy | Team accuracy | Qualification F1 | Missing recall |
|---|---:|---:|---:|---:|---:|---:|
| Sales | 47 | 0.9149 | 1.0000 | 0.8936 | 0.8877 | 0.9595 |
| Support | 33 | 0.8788 | 1.0000 | 0.9394 | 0.9438 | 0.9918 |

The local source is `ground-truth.xlsx`. This folder includes `ground-truth-frozen.csv`, an export of its 80 frozen rows for evaluation. Its frozen questions, history and interpretation gold were checked against the inputs and gold in this folder. Judge revisions to reference answers and tool traces do not affect these interpretation scores.

## Using the files

- Run downstream tests with `inputs.jsonl` and the Activity 2 fields needed from `predictions.jsonl`. Join them by `record_id`.
- Assess results against `gold.jsonl` for interpretation and `ground-truth-frozen.csv` for reference answers and citations. The CSV uses `id` for the same record key. Use the frozen set for evaluation and keep it out of prompts, few-shot examples and tuning.
- `per_record.jsonl` and `scores.json` capture the offline rescore. `gt-review-results-frozen.csv` contains the frozen rows from the judge review log.
