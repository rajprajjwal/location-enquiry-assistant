# Activity 20 — Enquiry reliability

The implementation passed the 50-scenario fault-injection acceptance check. These controlled synthetic tests measure reliability; answer quality and live latency are evaluated separately.

| Acceptance measure | Result | Status |
|---|---:|---|
| Task failure rate below 2% | 0/50 — 0% | Pass |
| Maximum retries per step | 2 | Pass |
| Token-budget overruns | 0 | Pass |
| Schema-valid final outputs | 50/50 — 100% | Pass |
| Unapproved actions applied | 0 | Pass |
| Declared failure paths tested | Fault scenarios and boundary tests below | Pass |

Fifteen transient faults recovered to the expected grounded draft. Thirty-five persistent faults or exhausted limits produced the expected schema-valid manual fallback. An unexpected escalation in a recoverable scenario would count as a task failure. Safe fallbacks are not counted as successful answers.

## Fault scenarios

Each row used five synthetic enquiry variants through the normal case runner, shared model client, registered tool interface and temporary SQLite persistence. Transport was injected below the client, preserving its retry and token checks. Diagnostic planning was disabled in this focused runner. No frozen or holdout cases were used.

| Injected fault | Expected outcome | Passed |
|---|---|---:|
| Transient model timeout | Grounded draft after retry | 5/5 |
| Persistent model timeout | Manual fallback | 5/5 |
| Malformed interpretation JSON, then valid repair | Grounded draft | 5/5 |
| Persistent malformed model JSON | Manual fallback | 5/5 |
| Transient document-tool error | Grounded draft after retry | 5/5 |
| Persistent document-tool error | Manual fallback | 5/5 |
| Invalid tool result | Reject result and return manual fallback | 5/5 |
| Exhausted cumulative token budget | Block dispatch and return manual fallback | 5/5 |
| Enquiry deadline exceeded by model response | Discard late response and return manual fallback | 5/5 |
| Tool wait timeout | Discard late result and return manual fallback | 5/5 |

## Implementation

- Pydantic validates reliability configuration and tool inputs/outputs. Existing response-schema validation remains in place.
- A shared query context carries retry credits, cumulative reservations and the enquiry deadline across interpretation, graph steps, tools and follow-up generation.
- Tenacity retries eligible chat transport failures. JSON repair and nested embedding retries consume the same step credits; hidden SDK retries are disabled.
- Tool workers have bounded waits. Expired workers cannot start further model or embedding calls through these controls. Only explicitly safe executors repeat.
- Every physical chat attempt reserves prompt tokens, requested output, metadata allowance and safety margin before dispatch. Traces persist counters and sanitized error events.
- Consequential actions remain pending human approval. Faults do not send responses or apply record changes automatically.

Defaults: two retries per step, 120-second enquiry deadline, 30-second model HTTP timeout, 15-second tool wait and 32,768 cumulative reserved tokens. The per-call context remains 8,192 tokens with at most 1,024 output tokens. See `copilot/config/reliability.yaml` and `docs/activity-20-reliability.md`.

## Failure-path coverage

Tests are in `tests/model_gateway/test_reliability.py`, `test_client.py`, `test_endpoint_contract.py`, and `tests/enquiry_workflow/test_tool_validation.py`.

| Failure path or invariant | Test evidence |
|---|---|
| Timeout, malformed JSON, tool error, invalid result, exhausted budget, late response | `test_faults_recover_or_return_the_expected_safe_fallback` |
| Invalid configuration and zero retries | `test_limits_reject_extra_fields_and_more_than_two_retries`, `test_zero_retry_configuration_does_not_wait_or_repeat` |
| Shared cumulative reservations | `test_nested_calls_share_cumulative_reservations` |
| Shared JSON repair/transport retry credits | `test_json_repair_and_transport_retries_share_the_step_limit` |
| HTTP 429/503 retry cap and non-retryable 500/authentication failure | Client backoff tests and `test_http_authentication_failure_is_not_retried` |
| Per-call context and tool metadata overflow | `test_context_budget_rejects_before_network`, `test_tool_definitions_and_prior_calls_count_toward_context` |
| Expired deadline, backoff and model-lock wait | `test_expired_deadline_stops_before_transport_and_rejects_long_backoff`, `test_model_lock_wait_obeys_the_enquiry_deadline` |
| Actual HTTP timeout arguments and SDK retry suppression | `test_http_timeout_uses_remaining_deadline_and_disables_sdk_retries` |
| Late tool result and blocked subsequent worker call | `test_late_tool_result_is_discarded_and_context_resets`, `test_timed_out_worker_cannot_start_another_model_request` |
| Unsafe executor not repeated | `test_tool_retry_requires_explicit_safe_registration` |
| Unregistered dispatch, invalid inputs and invalid tool outputs | `test_invalid_tool_inputs_and_results_do_not_retry`, registered-tool validation tests |
| Missing tokenizer assets | `test_tokenizer_configuration_failure_is_reported_without_network` |
| Concurrent enquiry isolation | `test_concurrent_enquiries_have_independent_budgets_and_thread_contexts` |
| Nested embedding retries cannot exceed shared cap | `test_nested_embedding_retries_share_the_tool_retry_limit` |

## Regression verification

The final offline run passed **423 tests and 15 subtests**, with one skipped freshness test because its real local snapshot is unavailable. Five existing RAG chunking tests were excluded because their BGE tokenizer could not be downloaded in the restricted network. They were not treated as passes. Existing dependency bundles were appended to the environment for the broader run; the commands, paths and earlier blocked attempts are recorded in `test-results.json`. `tests.txt` contains the final output.

The GT workbook checksum remains `13c9018a7ecec44bc240e4c1f884aaf31965b55280050250c2cb59c967253d68`. No Activity 19 evaluation results were rerun or overwritten.

## Tokenizer calibration and execution limits

One institute-endpoint probe reported **216 prompt tokens**, versus **215** from the official Qwen3 template. The local counter now includes the measured one-token framing allowance; a separate 64-token margin and metadata reservation protect admission conservatively. The probe was not repeated after calibration, so exact server parity across all request formats remains unverified. Raw evidence is retained in `token-probe.json`.

HTTP timeouts bound network phases and late responses are rejected; this is not an operating-system kill of a blocked SDK call. A tool wait timeout cannot forcibly terminate a running Python function. Registered app executors read, calculate or build pure proposals; external side-effect tools need separate cancellation and idempotency handling before registration.

## Saved evidence

- `summary.json`: acceptance totals.
- `faults.jsonl`: all 50 outcomes, counters and failure events.
- `token-probe.json`: raw endpoint comparison and calibration note.
- `test-results.json`, `tests.txt`: regression scope, outcomes and exclusions.
- `manifest.json`: source and artifact checksums.

Setup and rerun commands: `docs/activity-20-reliability.md`.
