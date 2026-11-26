# End-to-end tracing results

**80/80 frozen cases passed** the tracing acceptance check. Every workflow step was recorded locally, and local Langfuse received every saved span ID. The fixed working-eval sample passed 10/10, with no business-output changes in replay.

The frozen run recorded 1630 spans and 245 physical model attempts using BM25 retrieval. A separate embedding smoke check verified endpoint tracing and usage. These checks measure observability, not answer quality.

| Bucket | Runs passed | Median latency (ms) | P95 latency (ms) | Estimated reporting cost (INR) |
|---|---:|---:|---:|---:|
| capabilitycompare | 11/11 | 8155.3 | 12143.3 | 0.578551 |
| coveragecompare | 5/5 | 8574.9 | 11373.5 | 0.198829 |
| docs | 5/5 | 3273.1 | 6342.7 | 0.230403 |
| history | 5/5 | 10164.3 | 10434.3 | 0.185885 |
| interpretation | 5/5 | 11927.6 | 18147.1 | 0.368790 |
| limitscompare | 7/7 | 5318.2 | 7429.9 | 0.307389 |
| ownership | 11/11 | 6163.0 | 15690.0 | 0.342207 |
| pricecompare | 5/5 | 20755.3 | 29456.2 | 0.259478 |
| qualification | 15/15 | 11084.9 | 37477.0 | 0.725248 |
| updates | 11/11 | 9970.3 | 20702.9 | 0.559610 |

Total estimated reporting cost: **₹3.756390**. Actual institute endpoint charge: **₹0**. Estimates use $0.10 input, $0.20 output and $0.02 embedding per million tokens at ₹94/USD. These are illustrative assumptions, not billed prices.

Bucket, latency-ms and INR-cost filtering passed in the read-only trace viewer against the working-run database. Langfuse receives bucket metadata and native USD generation costs; INR estimates and actual-free-access fields remain available in root metadata.

Validation: 1,141 automated tests passed, 15 subtests passed, and one optional raw-snapshot freshness test was skipped because no local raw snapshot exists. The real-validator/observability check passed 181 tests and four subtests. Compilation passed. Focused lifecycle/case checks passed 19 tests after the final deletion-queue guard.

The pinned frozen inputs and GT are unchanged; holdout cases were excluded. Reference labels were trace metadata only. The source and cost lock is saved in `frozen-lock.json`.

Saved evidence:

- `working-verified/`: final ten-case replay-parity results and portable traces.
- `frozen-live/`: 80-case completeness results and portable traces.
- `verification/`: automated, embedding, viewer and deletion checks.
- `final-report.json`: exact bucket-level latency, cost and usage totals.

SQLite databases and local Langfuse credentials remain private runtime files. Historical `working-live/` results precede the illustrative rate card; do not treat them as final-price measurements. The interrupted `working-final/` attempt stopped during the initial export-timeout diagnosis and is superseded by `working-verified/`.
