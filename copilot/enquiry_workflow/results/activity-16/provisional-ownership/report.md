# Provisional ownership verification

Unknown customer status produces a provisional owner, a reason, a confirmation flag, and a suggested customer-status question. The workflow returns this information in ownership_review. The structured responsible-role reason also describes provisional ownership. The UI shows this information, and reopening the case restores it.

Explicit status deferrals remain unresolved across later follow-ups. They suppress the suggested status question until the customer supplies explicit status. The two deferred reply patterns from the review were covered by regression tests. Pending provider or API questions and the answer route continue through the existing workflow.

| Working-eval sample | Before | After |
|---|---:|---:|
| Development | 135/147 (91.84%) | 135/147 (91.84%) |
| Separate validation | 8/12 (66.67%) | 8/12 (66.67%) |

The validation replayed routine routing using saved interpretations and current working labels. It retained 11 recorded handoff decisions across the two samples. Of the 148 routine cases, 142 have provisional ownership. Ownership labels and model interpretation quality were not changed by this feature.

All 137 workflow tests passed with the real interpretation validator. Tests exercised the normal enquiry path, schema-valid outputs, unknown status, both deferred reply patterns, history, and case reopening. The two exact deferred frozen records were not rerun for scoring.

The entire workbook retained its prior SHA-256 hash, including all frozen GT. Frozen acceptance remains open.

The complete automated suite passed 346 tests. One corpus freshness check was skipped because the raw snapshot was unavailable.
