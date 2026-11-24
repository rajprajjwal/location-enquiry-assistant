# Ownership and escalation routing

The router assigns a responsible role and explains uncertainty. Escalations and record changes remain proposals requiring human approval.

## Approved policy

- Existing customers receive Support for routine pricing or technical guidance; new customers receive Sales qualification.
- Unknown customer status stays unknown. Explicit deployment quotes, licensing/reuse decisions and provider-feature discovery receive provisional Sales ownership. Generic feature inventories follow this rule even without a buying request.
- API documentation, numeric per-request feasibility, troubleshooting and published-rate arithmetic receive provisional Support ownership.
- Formal billing-policy handoffs use Sales. Clear incidents and reported address-quality issues follow the configured escalation categories.
- Deferred status stays deferred and does not trigger a repeated question.

## Input and saved state

In the UI, use **Confirmed customer relationship** only when supported by customer or account evidence. Leave **Use saved evidence / not confirmed** selected otherwise. The value is passed separately from the interpretation schema.

The case runner includes saved clarification messages in history and persists ownership evidence on the turn that establishes it. Reopening restores that evidence. Deleting the source turn rebuilds the relationship from remaining evidence, without leaking it to another case or leaving a copied confirmation in later snapshots.

For a pending customer-status question, the raw current reply determines the relationship on the same turn. The restored enquiry still drives interpretation, retrieval and escalation. Explicit new/existing replies are accepted; yes/no is accepted only for a single, unambiguous existing-customer question. Ambiguous replies and deferrals remain unconfirmed. The original reply is saved as evidence, so reopening and source deletion preserve this distinction.

## Components

- `copilot/safety/customer_evidence.py`: asserted relationship and actual-use evidence.
- `copilot/enquiry_workflow/ownership_status.py`: history, confirmed facts, uncertainty and deferrals.
- `copilot/enquiry_workflow/commercial_policy.py`: explicit quote and licensing/reuse decisions.
- `copilot/enquiry_workflow/feature_discovery.py`: provisional provider-feature ownership and technical capacity distinction.
- `copilot/enquiry_workflow/escalation.py`: ownership and reviewable handoffs.
- `copilot/model_gateway/request_gate.py`: local cross-process queue for the shared model key.

## Verification

The [final end-to-end report](../copilot/enquiry_workflow/results/activity-16/end-to-end-audit/report.md) records the acceptance result: **72/80 correct frozen owners (90%)**, escalation precision and recall **100%**, and escalation reasons **100%**. Frozen GT is unchanged and holdout cases were excluded.

Final scores use locked routing replay over fresh model outputs. Against unchanged working labels, owner accuracy is 269/286 (94.06%); seven labels disagree with the clarified feature-discovery policy and remain visible as mismatches. The report includes fresh-run commands for both `python` and `python3`, test evidence, remaining errors and source hashes.

The separate [combined integration check](../copilot/enquiry_workflow/results/workflow-review/combined-status-integration/report.json) verifies pending-reply binding, reopening and deletion. It does not replace the locked acceptance scores above or claim a new frozen evaluation.
