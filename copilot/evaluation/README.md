# Evaluation harness

Compare a plain-model prompting baseline with the existing agent using the same enquiry and chronological history. Generation receives no reference answer, rubric or expected labels. The scorer receives those fields separately. Every run saves predictions, individual scores, judge explanations, tool execution and provenance.

## Setup and run

Follow [deployment setup](../../docs/deployment.md) and [tracing setup](../observability/README.md). Activate Python 3.12, configure the shared chat client and embedding endpoint, prepare the pinned model assets and build the hybrid index. The corpus, GT and illustrative reporting rates are bound by hash. Runtime databases are isolated from staff cases.

One command produces both arms and all metrics on a working-eval sample:

```sh
python -m copilot.evaluation.runner --split working_eval --sample-per-bucket 1 --strategy zero_shot --mode hybrid --out results/evaluation/working-sample
```

Or:

```sh
python3 -m copilot.evaluation.runner --split working_eval --sample-per-bucket 1 --strategy zero_shot --mode hybrid --out results/evaluation/working-sample
```

Omit `--sample-per-bucket` to evaluate the established 317-case working pool. Use `--mode bm25` only for explicitly labelled lexical comparisons. Final hybrid runs use the existing top-30 reranking configuration with one passage per URL; this harness does not change retrieval behavior.

Reissue the same command to resume. Completed generations and scored records are reused, so a resume does not repeat them. Changed inputs, source code or configuration require a new output directory. An interrupted generation whose endpoint outcome is unknown stops for investigation rather than making a potentially duplicate holdout request.

## Select and verify the baseline

```sh
python -m copilot.evaluation.select_baseline --out results/evaluation/baseline-selection --mode hybrid
```

This compares zero-shot, few-shot, three-sample self-consistency and five-part decomposition with synthesis on ten grouped working-eval cases. The examples are synthetic. The highest automatic rubric accuracy wins; ties use the declared strategy order. Generation, source quotations and prices from the optional demonstration baseline are not reused.

Validate the winner on separate working groups. Baseline selection artifacts record the excluded validation groups. The validation and fresh-judge commands bind predictions to unchanged references. `copilot.evaluation.verify_judges` compares fresh judge scores on identical saved predictions; `copilot.evaluation.locking` refuses to lock a winner unless that check and deterministic saved-artifact aggregation pass. Frozen and holdout cases never select the baseline.

For a separate-group validation and repeatability check:

```sh
python -m copilot.evaluation.runner --split working_eval --sample-per-bucket 1 --selection results/evaluation/baseline-selection/selection.json --exclude-selection-groups --mode hybrid --out results/evaluation/working-validation
python -m copilot.evaluation.verify_judges --run results/evaluation/working-validation --out results/evaluation/working-validation/fresh-judge-repeatability.json
python -m copilot.evaluation.locking --selection results/evaluation/baseline-selection/selection.json --validation results/evaluation/working-validation --judges results/evaluation/working-validation/fresh-judge-repeatability.json --out results/evaluation/locked-selection.json
```

After a successful lock, run the unchanged frozen core:

```sh
python -m copilot.evaluation.runner --split frozen --selection results/evaluation/locked-selection.json --mode hybrid --out results/evaluation/frozen-paired
```

Only after the holdout review is complete, the final protected command is:

```sh
python -m copilot.evaluation.runner --split holdout --final-holdout --selection results/evaluation/locked-selection.json --holdout-approval results/evaluation/holdout-review.json --mode hybrid --out results/evaluation/holdout-final
```

All module commands work with `python3` in place of `python`.

## Metrics

| Metric | Meaning and denominator |
|---|---|
| Answer accuracy | Automatic reference/rubric score, averaged over scored cases. A failed generation remains a zero rather than disappearing. |
| Grounding | Automatic support assessment for claims actually made, using source evidence; omitted content affects completeness. |
| Citation coverage | Fraction of substantive drafts with at least one source-bound, supported citation. |
| Citation precision | Supported, source-bound citations divided by scored predicted citations. This is weighted by citation count. |
| Comparison completeness | Required providers, dimensions, equivalent requirements and assumptions; applicable comparison cases only. |
| Qualification completeness | Strict agreement for each qualification field and the missing-field set. Keys must be present; unknowns must remain null, monthly volume compares quantity/unit rather than raw wording, and other free text uses normalized exact agreement. Paraphrases receive no inferred credit. The model’s separate qualification estimate is diagnostic only. |
| History use | Reuse of supplied history and avoidance of repeated checks; cases with history only. |
| Owner / next action | Exact match to the unchanged gold owner and action type. |
| Tool execution | Successful registered, input-valid and output-valid calls divided by actual calls; separate from answer quality. |
| Expected tool coverage | Successful tool types against raw GT expectations. Calculator maps to provider comparison; record updates map to the sandbox proposal tool. Handoff routing is evaluated as an action, not a fictitious registered tool call. |
| Span Recall@1/5/10 and MRR | Independent top-ten retrieval probe against verbatim gold spans on the correct canonical source. Duplicate labels collapse; unmatched spans remain in the denominator. Summary labels are counted separately and excluded from these strict metrics. |
| Source Recall@1/5/10 | Independent probe against distinct canonical gold URLs. This does not imply passage relevance. |
| Latency and cost | Generation elapsed time in milliseconds and endpoint-reported usage. Judge and retrieval-probe overhead are reported separately. |

Most quality metrics are scored-case averages; citation precision and tool success use citation/call weights. Every metric exposes its scored-case count and unit denominator. Not applicable or unscored is `null`, not zero. Plain-model retrieval and tool metrics are not applicable. Judge errors remain visible as unscored dimensions and run errors.

Answer accuracy, grounding, comparison completeness and history scores are automatic model judgements; qualification is scored deterministically from typed fields. These automatic judgements are not independently verified human scores. Calibration checks reference and empty controls; fresh-judge repeatability checks numerical stability. These checks do not establish human agreement or resolve disputed gold labels. A 1% tolerance means **one percentage point** on a 0–1 metric. Saved-artifact reaggregation is exact; fresh generation latency and token counts naturally vary and are not claimed byte-identical.

Actual institute endpoint access is free. Reporting estimates use the configured illustrative rates at ₹94/USD. The native Langfuse cost fields are USD; the dashboard uses INR.

## Frozen and holdout protection

Frozen inputs must still match the pinned 80-case export. Use a verified locked baseline selection for a frozen run; frozen GT is never edited by the harness.

A final holdout run additionally requires a complete hash-bound reference/rubric/source review, reasoned decisions for every flagged cross-split pair, and a locked working-eval selection. The previously approved frozen twin is always excluded. The global holdout ledger permits one final output directory; only an exact resume of that run is accepted. Holdout results must not be used to revise prompts, retrieval or scoring.

The harness does not treat workbook rows marked `pending` as independently approved gold. A review form and unresolved-pair list must be completed before final holdout acceptance. Synthetic and working-eval checks can proceed without consuming holdout.

## Saved files

- `manifest.json`: data, source, corpus, rates and configuration bindings.
- `cases.jsonl`: input/reference snapshot used by this scorer.
- `generations.jsonl`: completed generation journal, allowing scoring to resume without new generation calls.
- `records.jsonl`: paired predictions, tools, retrieval diagnostics, judge results and final per-case metrics.
- `summary.json`: versioned aggregates by bucket, API and team, consumed by the dashboard.
- `repeatability.json`: exact saved-artifact metric reaggregation result.
- `cases.db`: ignored local case, approval and trace state; no production writes or messages.

Citation verification accepts indexed passages, observed retrieved excerpts and the version-bound pricing evidence used by the calculator. It rejects a pricing snapshot tied to another corpus. This is source verification, not an extra retrieval step for baseline generation.
