# Enquiry workflow review

All 11 pipeline handoffs have been reviewed. Activity 14 acceptance remains open: the final 317-case working-eval run scores **55.83% question F1**, below the 80% target, with **52.44% fact coverage**. GT remains unchanged; frozen and holdout cases were excluded.

| Step | Responsibility | Verified outcome and remaining gap |
|---|---|---|
| 1 | Validate enquiry and restore case history | Intake, reopen and case-isolation regressions pass. |
| 2 | Bind facts, provider roles and estimate assumptions | Active-task evidence, explicit corrections, quantities, storage, session termination and travel modes are separated from documentation and conditional estimates. |
| 3 | Classify API and intent | Working API accuracy 96.85%; intent accuracy 79.50%. Remaining mismatches are saved. |
| 4 | Select answer, clarification or escalation | Complete control audit saved. Earlier interpretation and provider-blocker changes affect some baseline routes; subsequent follow-up fixes preserve controls across all 317 cases. |
| 5 | Retrieve and pass relevant evidence | Planning receives exact bounded excerpts with provider diversity. Search indexes and ranking configuration were not changed. |
| 6 | Draft precise, grounded guidance | Checklist advice and structured questions share a requirement plan. A new final answer-rubric acceptance run is still pending. |
| 7 | Validate final outputs | All 317 final envelopes are schema-valid. Requirement-plan binding and selected-question completeness are checked after question assembly. |
| 8 | Select material missing requirements | Provider and billed-operation gates remove repeated or irrelevant questions. Narrow and mutually exclusive menus still leave coverage gaps. |
| 9 | Render and score complete questions | Final precision 59.82%, recall 52.34%; 67 whole-question matches and 86/164 required facts. The 80% F1 target is not met. |
| 10 | Preserve ownership, approvals and pending replies | Completed ownership work retained. Raw current relationship replies are separated from restored tasks; same-turn corrections, reopen, deletion and pending approval checks pass. |
| 11 | Bind references and evaluate | All 317 predictions and semantic judgements are hash-bound. Original GT and separately reviewed question policies disagree and remain separately reported. |

The final production test suite passes 1,122 tests and 15 subtests. One freshness test is skipped because its expected local snapshot is absent; this is recorded rather than counted as a pass.

Next, address answer-materiality and multi-decision coverage gaps on working-eval, and reconcile the question-reference policy in a separately reviewed version. Lock the configuration before frozen rubric/F1 acceptance and the human spot-check. Retain the existing GT and historical scores for comparison.

See the [full working-eval report](../copilot/response_drafting/results/activity-14/workflow-review/README.md), [control audit](../copilot/response_drafting/results/activity-14/workflow-review/final-control-verification.json), and [combined ownership integration](../copilot/enquiry_workflow/results/workflow-review/combined-status-integration/report.json). Earlier intake evidence remains in `copilot/enquiry_workflow/results/intake-review/README.md`.
