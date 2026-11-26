# Working-eval routing experiments

We compared the same 159 working-eval records: 147 development cases and 12 separate validation cases. Both versions used the current approved labels and saved interpretations. Routine routing was replayed, retaining 11 saved model handoff decisions. Reports reuse the existing groups and folds. This is a paired replay, not a fresh generalization benchmark.

| Configuration | Correct owners | Owner accuracy |
|---|---:|---:|
| Baseline | 143/159 | 89.94% |
| Actual use | 143/159 | 89.94% |
| Provider discovery | 142/159 | 89.31% |
| Combined | 142/159 | 89.31% |

Actual-use detection made no ownership changes in these working cases. Positive and negative controlled tests verify that current API use establishes existing status while planned, hypothetical, historical, and negated use do not. The actual-use detector is enabled.

The provider-discovery fallback corrected three owners and introduced four errors. Technical feature questions about plus codes, travel modes, address inputs, and precision indicators regressed to Sales. The broad discovery fallback remains disabled.

Confirmed customer status is read from the case fact named customer_status, using existing, new, or unknown. These facts must describe the customer relationship for the service in the case. Tests create these facts in a temporary database, reopen the case, and verify Support or Sales routing through run_case. This feature supplies a route for confirmed case evidence; it does not add account facts to the evaluation records.

Follow-up tests verify short Existing/New replies to a customer-status question, retention across turns, and an explicit correction to a case fact. Both deferred replies remain provisional with no repeated status question.

All 68 targeted tests passed with the real interpretation validator. The broader workflow run exposed an unrelated Streamlit mock limitation: the fixture assumes every model JSON request contains passages, but the diagnostic planner sends a different payload. This prevents reporting a completely passing UI suite.

The entire GT workbook retained its SHA-256. No frozen or holdout cases were used in these experiment scores, and no frozen evaluation was run.
