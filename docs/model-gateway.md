# Model gateway

Capstone tracking: Activity 18.

The shared client lives in `copilot/llm/client.py`. Activity 2's existing call remains valid. Other components can supply optional `tools`, `tool_choice`, and `response_format` to `LLMClient.complete()`.

| Input | Meaning |
|---|---|
| `messages` | OpenAI-compatible messages. Assistant tool calls and tool-result IDs are preserved. |
| `max_tokens`, `temperature` | Completion limit and generation setting. The endpoint limit is 1,024 output tokens and 8,192 combined context tokens. |
| `tools`, `tool_choice` | Function definitions and tool selection. A tool choice requires definitions. |
| `response_format` | Endpoint output mode, such as `{"type": "json_object"}`. |

The returned `Completion` has `text`, `raw` (the same redacted text), `model`, endpoint `usage`, `latency_ms`, `think_seen`, normalized `tool_calls`, and `finish_reason`. Each tool call retains its ID, type, function name and arguments string. Callers parse arguments and validate the registered tool schema before execution. Endpoint errors use the existing `ConfigError`, `LLMError`, `TokenLimitError`, and `BudgetExceeded` exceptions. Context preflight uses the existing character-based estimate and includes tool definitions and tool-message metadata. Exact tokenizer enforcement belongs to Activity 20.

Configuration uses `TRACKB_API_KEY` and `TRACKB_CA_CERT` or explicit client constructor arguments. An app adapter can pass its configured credentials explicitly. TLS verification uses the provided CA certificate. Latency covers the complete logical SDK call including waits for serialization and retry backoff. The existing three-retry policy needs alignment with Activity 20's per-step retry target.

## Endpoint verification

Run synthetic chat, JSON-object mode, and a forced function-call probe.

```bash
python -m copilot.llm.endpoint_checks --out model-gateway/results/smoke-002
```

After the probes pass, the following also sends the 80 frozen enquiries and their conversation history to the configured endpoint. It checks the input checksum and record IDs first.

```bash
python -m copilot.llm.endpoint_checks \
  --frozen-dir eval/frozen-interpretation \
  --out model-gateway/results/frozen-002
```

Each run uses a new output directory and writes `report.json`. A frozen run also writes `responses.jsonl`. Reports distinguish smoke latency from the full frozen latency population. p50 and p95 use nearest-rank percentiles of completed calls. Error cases are counted separately through the per-case pass fields. The frozen run measures endpoint completion behavior and latency. Answer accuracy uses the evaluation harness.

## Model evidence

The institute endpoint is configured for `Qwen/Qwen3-8B`. Qwen's model card reports **8.2B total parameters** and **6.95B non-embedding parameters**. On 20 November 2026, the project owner accepted this model because it was supplied by the institute. The report retains the strict parameter-count check as false and records project model acceptance separately; the parameter counts have not been changed. [Official model card](https://huggingface.co/Qwen/Qwen3-8B)

Live smoke results, frozen latency and overall acceptance are recorded only after their respective runs. The presence of the model name in config and passing offline tests provide integration evidence. The endpoint's returned model ID is checked during live probes.

## Verified status

The first live synthetic run passed chat, JSON-object mode and function-call checks. The evidence is in `model-gateway/results/smoke-001/report.json`. Across these three synthetic calls, p50 was 430 ms and p95 was 714 ms; these are smoke timings, not frozen-set timings. The 80-case live run is complete: all 80 endpoint checks passed, with p50 2,680 ms and p95 5,463 ms. Evidence is in `model-gateway/results/frozen-001/report.json` and `responses.jsonl`. Activity 18 is complete under the project owner's acceptance of the institute-provided model. The stored acceptance decision was updated without rerunning the endpoint or changing measured results.

The CLI exits with status 0 only when every Activity 18 acceptance condition passes. A passing smoke-only run therefore still exits with status 1; inspect `smoke_passed` for the individual smoke result.
