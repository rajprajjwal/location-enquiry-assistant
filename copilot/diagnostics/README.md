# Shared diagnostic facts

The diagnostic contract carries customer-supplied facts, provenance, completed checks and question status.
The same state is available during interpretation, case persistence and staff follow-up planning.
The JSON Schema is available in `contracts/diagnostics/state.schema.json`.

Interpretation keeps its existing public input and output schemas. Its optional diagnostic context is
validated and projected onto supported qualification fields. Operational facts retain their own identifiers,
such as `http_status`, `request_example` and `result_filters`.

The workflow returns retrieved passages alongside its draft. Follow-up planning receives a bounded
selection of those passages, the draft and the shared facts. The model proposes a diagnostic decision.
An applicability policy checks that decision against customer evidence. Fixed templates group the missing
facts for one diagnostic decision and request redacted examples. Named response statuses, including
`REQUEST_DENIED`, retain their observed value and source. An unresolved customer denial calls for
the redacted request. A possible cause in retrieved documentation is not treated as a confirmed
customer configuration. Definition questions and explicit known causes retain documentation guidance.

Pricing comparisons publish regional price requirements from `pricing_tools/qualification.py`.
The planner asks for billing country and primary usage geography only when needed to qualify
the price schedule. Supplied facts, explicit pricing assumptions and declined questions are
respected. This produces a staff suggestion while retaining the active clarification and pending reply.

Staff suggestions remain suggestions until they are asked. Active clarification questions are tracked as
asked, and their existing pending-reply mechanism continues to handle replies.
Older cases rebuild diagnostic facts from their saved user messages when reopened.

Provider names retain separate meanings. `mentioned_providers` preserves every named option;
`provider` is an unambiguous documentation or diagnostic target; `current_provider` requires
evidenced customer use or an explicitly bound clarification answer. A comparison does not select
a provider. Retractions clear stale current-provider facts when the case is reopened.

Documented allowances do not supply customer workload. Explicit estimate quantities remain
scenario assumptions, separate from asserted usage. Newer evidenced customer corrections can
replace older facts; assistant messages cannot establish customer facts.

Evaluation reviews must be bound to the SHA-256 hashes of both the predictions and the locked labels.
The scorer rejects stale reviews, invalid match indices and full-question matches without all required
atomic facts. Semantic match judgements are supplied by a named reviewer for each run.
