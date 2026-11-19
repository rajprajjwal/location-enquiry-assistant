# Activity 5 gold-data validation audit

Audit date 18 November 2026

| Acceptance check | Verified result | Status |
|---|---|---|
| Eval / holdout target 400 / 100 | 429 / 103, including 80 frozen eval cases | Above target by 29 eval and 3 holdout |
| Zero template families shared across splits | 0 shared families, 0 missing family values | Pass |
| No pair at embedding cosine ≥ 0.90 | 153 of 141,246 pairs flagged | Fail, review required |
| Review evidence on high-priority records | 246 high-priority cases, 0 with recorded second-pass date and evidence | Pending |
| Recorded gold approvals | 0/532 approved in the workbook | Pending |

## Similarity findings

| Pair type | Cosine ≥ 0.90 | Normalized exact-text matches |
|---|---:|---:|
| Across eval and holdout | 17 | 0 |
| Within eval | 110 | 0 |
| Within holdout | 26 | 0 |

The flagged pairs form 40 connected groups involving 127 unique cases. The highest cosine was 0.999211. The cross-split pairs involve 12 distinct eval cases and 7 distinct holdout cases. Cross-split pairs involving a frozen case: 1. Similarity flags are candidates for human review. A connection through an intermediate case gives reviewers a shared group to inspect.

## Review files and open decisions

- `activity-5-duplicate-review.csv` lists candidate pairs and puts cross-split cases first. Review those pairs with the holdout custodian, then decide which other flagged cases are genuine duplicates.
- `activity-5-review-queue.csv` has the record IDs and fields for first-pass, second-pass, and disagreement evidence. The tracker calls for two independent reviews of pricing, policy, and escalation cases. The repo spec documents a first pass and second self-review by Shahid for high-priority cases. Confirm which rule will be used for acceptance and record the reviews.
- Resolve the 400 / 100 target after duplicate adjudication. If the exact counts are required, retain all 80 frozen cases and preserve holdout isolation when selecting the final evaluation subset.

## Reproducibility

- Workbook SHA-256 `59518ab0d5df4a7d4ed176603b78e9b247352581f66e63496c972179bf770113`.
- Local embedding model [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Model SHA-256 `6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452`. Tokenizer SHA-256 `be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037`. ONNX Runtime 1.32.0, tokenizers 0.23.3.
- Embedded the current and earlier user turns in chronological order. Used attention-mask mean pooling and unit normalization, then compared every unordered pair. Model token limit 256. Records truncated 0.
- The workbook and frozen membership were verified by hash and ID. The audit files use record IDs and review metadata. Embedding inference ran locally.
