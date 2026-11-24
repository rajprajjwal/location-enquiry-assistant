# Ownership context review

The form contains eight remaining mismatching frozen cases. It hides the current owner prediction and gold owner so a reviewer can judge the query and history first. A mismatch does not prove the gold label is wrong.

1. Record customer status as `existing`, `new`, `unknown`, or `deferred`. Cite actual supplied evidence. A named provider, a new SKU, a new project or forecast traffic alone does not establish the customer relationship.
2. Select the requested work: `product_selection`, `deployment_quote`, `licensing_decision`, `billing_policy`, `api_documentation`, `troubleshooting`, or `published_rate_calculation`.
3. Apply the approved policy. Confirmed existing service guidance uses Support; new-customer qualification uses Sales. Billing-policy handoffs use Sales. For unknown status, Sales provisionally handles product/provider selection, deployment quotes and licensing decisions; Support handles API documentation, troubleshooting and published-rate calculations.
4. Give the provisional owner and rationale separately from customer status. Do not invent account facts to reproduce a label. For DIR-020 and DIR-021 retain the deferral and do not ask the status question again.

This is a proposed review artifact, not a change to the frozen ground truth. If the original label and approved policy differ, record the disagreement for adjudication. Any revised policy reference must be versioned separately and evaluated against the original labels as well; a new policy score must not be reported as improvement against unchanged gold.
