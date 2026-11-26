# Model gateway frozen endpoint verification

Capstone tracking: Activity 18.

Run date: 20 November 2026 (Asia/Kolkata).

- Input: the 80 frozen records in `eval/frozen-interpretation/inputs.jsonl`, including conversation history for five records. Gold answers and labels were not included in the model requests.
- Input checksum and ordered record IDs verified against the frozen manifest.
- Synthetic chat, JSON-object mode and forced function-call probes: all passed.
- Frozen endpoint checks: **80/80 passed**; no request errors, empty responses, model-ID mismatches or output-limit truncations. All finish reasons were `stop`.
- Latency: **p50 2,680 ms**, **p95 5,463 ms** across 80 completed logical calls, using nearest-rank percentiles.
- Generation: temperature 0, maximum 512 output tokens, thinking disabled via `chat_template_kwargs`.
- Endpoint-reported batch usage: 5,721 prompt tokens, 10,476 completion tokens, 16,197 total tokens. Monetary cost has not been calculated.

This run used a concise drafting prompt to measure endpoint completion and latency. It did not run the Activity 2 interpretation pipeline or score frozen-set answer accuracy, grounding, qualification or tool execution. Separate synthetic probes checked JSON and tool-call support.

The model card reports Qwen3-8B as 8.2B total parameters and 6.95B non-embedding parameters. On 20 November 2026, the project owner accepted the institute-provided model for this project. The strict parameter-count check remains false as a factual record, while project model acceptance is recorded separately. The overall `activity18_passed` flag is now true based on that acceptance and the successful endpoint checks. No model calls were rerun and no responses or timings were changed.

Evidence: `report.json` and `responses.jsonl`. The original frozen inputs, gold labels and interpretation scores were not changed. Responses are unscored model drafts and must not be treated as reference answers.
