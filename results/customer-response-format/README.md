# Customer response format verification

The case service adds a separate `customer_response` with versioned Markdown sections. The UI and local query runner show the same answer, supporting details, assumptions or active questions, next steps and source links. Empty sections are omitted. Structured comparisons and deterministic price rows use tables. Source claims, code examples, pricing assumptions and unverified-evidence flags are retained.

Formatting adds no model calls and leaves the seven structured outputs, route, owner, active questions, pending-reply controls and approvals unchanged. Pending proposals remain visibly pending. Invalid final output is shown as needing review, while internal error details stay in the staff view. The response is a snapshot at processing time; later approval decisions appear in the approval log.

## Verification

- 1,147 automated tests passed; 15 subtests passed. The existing freshness check skipped because no dated raw-source snapshot is available. No tests were excluded.
- Live synthetic checks covered a definition, provider clarification and reply, a pricing table, a pending record update, a pending incident handoff and hybrid documentation guidance.
- The record remained unapplied and the incident approval remained pending. Live workflow checks used temporary databases. Two additional demonstration enquiries used the testing instance's case database to verify the chat bridge.
- A cold hybrid search initially exhausted its tool retries. Runtime warm-up now initializes a complete hybrid retrieval before the enquiry deadline, once per process. The final hybrid case passed; it still needed two bounded search retries, recorded in `summary.json`. Timeouts and ranking settings were not increased or changed.
- No frozen or holdout data was scored and no production messages or writes were performed.

`summary.json` records results and source hashes. `live-final-pricing.json` shows the final price headline and table. `hybrid-warmed/` contains the successful hybrid response and workflow diagnostics. Earlier failure logs are retained so the observed startup and environment issues remain visible.

The initial full test attempt lacked the configured model cache. `full-tests-configured.txt` and `final-tests.txt` use the deployment's `HF_HOME` and pass all available tests.

For chat testing, use `copilot.enquiry_workflow.console` as documented in the workflow guide. It calls the same case service and database as the UI. Reuse the returned case ID for follow-up replies.
