# Enquiry reliability

Activity 20 adds shared limits around interpretation, model calls and registered tools. A failed dependency returns a schema-valid manual fallback; transient failures must recover to the expected draft.

## Controls

| Control | Default | Behaviour |
|---|---:|---|
| Retries per step | 2 | At most three physical attempts. JSON repair shares the same retry credits as transport retries. |
| Enquiry deadline | 120 seconds | Shared across interpretation, orchestration and follow-up generation. |
| Model HTTP timeout | 30 seconds | Uses the smaller of this limit, the client timeout and remaining enquiry time. |
| Tool wait timeout | 15 seconds | Late results are discarded. |
| Cumulative token reservation | 32,768 | Every physical model attempt reserves its full input and requested output before dispatch. |
| Per-call context | 8,192 tokens | Includes the rendered prompt, requested output, metadata allowance and 64 safety tokens. Output remains limited to 1,024 tokens. |
| Workflow steps | 10 | Existing bounded LangGraph loop remains in place. |

Change defaults in `copilot/config/reliability.yaml`, then restart the application. More than two retries is rejected by Pydantic. HTTP 429/503 and transport timeouts/connections use Tenacity with two- and four-second backoffs. Authentication and other non-retryable errors fail immediately. Only tools explicitly marked `retry_safe` can repeat; document search, comparison and the app's pure record proposal qualify. The legacy mock-store writer does not repeat.

Nested embedding requests share the same retry credits and deadline during an enquiry; bulk index rebuilds retain their existing policy. The query context follows graph steps and tool workers. Both `run_case()` and `run_enquiry()` return a `reliability` object with reservations, reported usage, attempts, retry counts, events and elapsed milliseconds. Case traces persist the same counters. Diagnostic planning stays enabled by default in the app.

## Token counting

The client uses the published Qwen3 tokenizer and chat template, with pinned SHA-256 checks. Legacy character estimates remain in historical interpretation trace fields; they no longer control admission.

One representative endpoint probe, including a tool definition and prior tool-call metadata, reported 216 prompt tokens versus 215 from the published template. The local counter adds the measured one-token framing allowance and reserves an additional 64 safety tokens plus metadata. This is a calibration from one call, not independent proof of exact server counts for every request format. The raw mismatch is retained in `token-probe.json`.

Reservations are conservative and are not refunded, including failed attempts whose usage the server did not report. Reported usage is therefore separate from reserved tokens. Budget exhaustion prevents another model request; it does not ask the model to shorten a response after dispatch.

## Setup and verification

From the repository root, use the existing project environment:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m copilot.model_gateway.prepare_tokenizer
```

The equivalent Python 3 commands are:

```bash
.venv/bin/python3 -m pip install -r requirements.txt
.venv/bin/python3 -m copilot.model_gateway.prepare_tokenizer
```

The setup command downloads only the two official tokenizer assets and checks their pinned hashes. Assets are ignored by Git. For an external writable asset directory, set `TRACKB_TOKENIZER_DIR` before setup and application startup. A missing or changed asset causes a configuration fallback before any endpoint call. Re-running setup verifies already-installed files without downloading them.

Run the offline 50-scenario check into a new results directory:

```bash
INTERPRET_VALIDATION=real .venv/bin/python -m copilot.enquiry_workflow.verification.reliability_faults --output copilot/enquiry_workflow/results/activity-20-rerun
```

Or:

```bash
INTERPRET_VALIDATION=real .venv/bin/python3 -m copilot.enquiry_workflow.verification.reliability_faults --output copilot/enquiry_workflow/results/activity-20-rerun
```

This runner uses synthetic enquiries, deterministic document evidence, temporary SQLite databases and injected transport responses. It makes no network requests and uses no frozen or holdout data. Diagnostic planning is disabled in this focused runner to isolate reliability; the normal app default is unchanged. Five wording variants exercise each of ten fault classes.

Focused regression command:

```bash
INTERPRET_VALIDATION=real .venv/bin/python -m pytest -q tests/model_gateway tests/enquiry_interpretation tests/enquiry_workflow
```

Replace `.venv/bin/python` with `.venv/bin/python3` for the equivalent command. Live enquiries still require the normal model credentials, CA certificate and configured retrieval dependencies.

## Acceptance and evidence

The 50-run check requires a task failure rate below 2%, at most two retries per step, zero token-budget overruns and covered failure paths. With 50 runs, even one unexpected failure is 2% and fails acceptance. A transient fault that unexpectedly escalates counts as a failure. A persistent fault passes only when it produces the expected valid manual fallback without applying an action.

Saved evidence is in `copilot/enquiry_workflow/results/activity-20/`: `summary.json`, `faults.jsonl`, `token-probe.json`, `test-results.json`, `manifest.json` and `report.md`. Earlier evaluation reports and frozen GT are unchanged by this activity.

## Execution limits

HTTP timeouts bound network phases, and deadline checks reject late model responses. They are not an operating-system kill of a blocked SDK call. The tool timeout stops waiting, discards its result and blocks further controlled calls from that worker; Python cannot forcibly stop an already-running function. Registered app tools perform reads, calculations or pure proposals, while consequential changes remain behind human approval. Do not register external side-effect executors under these worker/retry controls without separate cancellation and idempotency handling.
