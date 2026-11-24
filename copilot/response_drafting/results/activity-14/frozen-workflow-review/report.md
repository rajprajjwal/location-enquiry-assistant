# Activity 14: updated frozen evaluation

The updated implementation was run once on the same **80 frozen GT cases**. Clarifying-question F1 is **28.57%** and required-fact coverage is **34.34%**. Both improve over the previous frozen run, but the **80% question-F1 target is not met**.

| Metric | Previous frozen run | Updated frozen run |
|---|---:|---:|
| Clarifying-question F1 | 13.22% | **28.57%** |
| Fact coverage | 18/99 (18.18%) | **34/99 (34.34%)** |
| Whole questions matched | 8/75 | **17/75** |
| Question precision | 17.39% | 38.64% |
| Question recall | 10.67% | 22.67% |
| Questions produced | 46 | 44 |
| Questions on empty-reference cases | 24 | 16 |

F1 is `2 × 17 / (44 + 75)`. Fact coverage is `34 / 99`. All 80 cases remain in the evaluation, including cases with empty reference lists or no generated questions. This is a frozen-set result; the earlier 317-case working-eval result uses a different cohort and reference.

## Evaluation policy

The original 75 question groups and the same 99-fact decomposition are unchanged. Whole matches require one-to-one semantic equivalence, all required facts and equivalent decision granularity. Bundling an extra independent decision does not automatically earn a whole-question match. Partial facts count separately, once per reference question and fact. Supplied facts, internal field IDs and draft prose alone receive no question credit.

Two assistant reviews covered all 80 cases and agreed on every whole-question and atomic-fact judgement. Reviews are bound to exact prediction, reference and per-case hashes. This is assistant-reviewed scoring, not an independent human spot-check.

## Execution and integrity

- Same ordered 80 frozen inputs: 20 per API; no holdout cases selected or scored.
- Current complete case pipeline, including history restoration, interpretation, follow-up planning, final validation and sandbox state.
- Institute-provided Qwen3-8B endpoint; zero-shot interpretation; BM25 retrieval without reranking, matching the earlier frozen configuration.
- **244 fresh completion calls**, zero cached calls and zero recorded logical model-call or execution errors.
- **80/80 schema-valid outputs**. There were 65 final-answer statuses and 15 escalation/fallback statuses; those statuses are not answer-quality scores.
- Original frozen input bytes, GT export, question labels, fact labels and local GT workbook remain unchanged. The locked application, prompt, configuration, tokenizer and corpus files also passed the post-run integrity check.
- No application fixes, relabelling, case exclusions, score-based reruns or synthetic customer replies were introduced from these frozen results.

The implementation includes the completed ownership work. Against the prior frozen run, active questions and pending replies are unchanged in all 80 cases. Historical ownership and response differences are recorded in `prior-frozen-control-comparison.json`; they reflect the combined updated implementation and fresh model requests, rather than an isolated causal test of one fix. Proposed sandbox changes retain their approval status.

## Saved results

- `scores.json`, `summary.json`: final metrics and comparison.
- `predictions.jsonl`, `model-calls.jsonl`, `cases.db`: complete outputs, fresh requests/responses and sandbox traces.
- `locked-gold.json`, `frozen-questions.json`, `inputs.jsonl`, `ground-truth-frozen.csv`: unchanged references and input copies.
- `implementation-lock.json`, `runtime/`, `integrity-verification.json`, `post-run-integrity-audit.json`: frozen code/assets and integrity evidence.
- `primary-review-*.json`, `independent-review-*.json`, `review-crosscheck.json`, `question-review.bound.json`: semantic judgements and exact bindings.

Reproduce the saved score without model access using either command from the repository root:

```sh
python copilot/response_drafting/results/activity-14/frozen-workflow-review/rescore.py
```

```sh
python3 copilot/response_drafting/results/activity-14/frozen-workflow-review/rescore.py
```

Activity 14 remains open. This run reports the updated frozen scores; it does not change the GT or use frozen results to tune the implementation.
