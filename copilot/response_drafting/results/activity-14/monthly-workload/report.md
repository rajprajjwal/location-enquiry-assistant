Monthly-workload normalization — working-only verification

A non-null monthly_volume object no longer means monthly API usage is known. copilot/qualification/workload.py checks for usable quantities with explicit monthly workload units. copilot/qualification/facts.py applies that check when merging interpretation or stored facts and admitting model-proposed monthly facts.

A saved value such as raw="15–20 outlets", requests_per_month=null and unit=null remains incomplete. It cannot suppress the monthly-workload question. The outlet count remains available separately as route-size information. If the enquiry separately states 20,000 requests per month, that API workload is recovered without confusing it with the outlet count.

Recognized requests, calls, sessions, lookups, elements and matrix-operation counts retain their units. Sessions are not multiplied by keystrokes, and matrices are not multiplied by origins and destinations here. A daily rate is not converted to a monthly rate using an unstated assumption. Bare counts with an unknown unit, invalid numeric values and scalar-incompatible ranges do not become confirmed monthly quantities. A consistent structured stored count with an explicit monthly workload unit remains usable.

The original interpretation output and routing logic are unchanged. The fix changes qualification usability and staff question suppression. Partial values remain visible before question rendering; they do not cause an asked workload question to be marked answered merely because a raw value exists.

Verification results:

| Check | Result |
| --- | ---: |
| Existing working-eval contexts audited offline | 36 |
| Previously supplied unusable outlet-count values invalidated | 1 — DIR-049 |
| Previously numeric workload counts preserved | 18/18 |
| Numeric count regressions in that audit | 0 |
| Live before-and-after working enquiries | 5 |
| Route and pending-state snapshots preserved | 5/5 |
| Pending conversations reopened identically | 4/4 |
| Targeted automated tests | 364 passed, four subtests passed |

The live check used DIR-049 plus AC-233, DM-228, RG-227 and RG-228. In the fresh live DIR-049 pass, the model already asked for monthly volume in both methods, so that pass does not demonstrate a before-and-after answer improvement. The saved failing context and deterministic full qualification-planner test reproduce the original suppression error and verify the correction, including an attempted model proposal of the same invalid outlet count.

The offline 36-context audit is a normalization audit, not a new end-to-end benchmark. No new 36-case F1 or fact-coverage score was calculated. The previous F1 0.840 and fact coverage 69/84 remain the last full comparison, measured before this normalization step. The plan-validation fixes, working-label review and subsequent full 36-case rescore remain separate pending steps.

All live route, next-action, owner, approval, active-question, pending-reply and saved clarification-history comparisons matched. The final five-case check recorded no endpoint errors or excluded attempts. The source hashes were unchanged during final verification, and the local GT workbook byte hash is unchanged. No frozen or holdout records were used or scored.

Saved evidence includes normalization-audit.json, workflow-check.jsonl, workflow-check.json, results.json, run-manifest.json and tests.txt. The initial smoke check is retained separately. The qualification module README describes workload.py and its integration.
