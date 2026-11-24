# schemas/

Versioned JSON Schemas (draft 2020-12, `x-spec-version` 1.0.0) for the copilot's output. Each schema also carries a short top-level `"$comment"` (purpose, use case, example); `$comment` has no effect on validation.

| File | Defines | Key rule (example) |
|------|---------|--------------------|
| `envelope.schema.json` | Wrapper for one answer: record metadata + all 7 outputs. | `step_count_limit` 10, `output_token_budget` 1024. |
| `response_draft.schema.json` | Output 1: reply text with citations. | Each citation needs `url`, `span`, `supports_claim`. |
| `clarifying_questions.schema.json` | Output 2: questions to ask. | `needed=true` ⇒ at least one question. |
| `qualification_details.schema.json` | Output 3: sales qualification. | Required: `use_case_api`, `region`, `monthly_volume`, `current_provider`, `timeline`. |
| `proposed_record_update.schema.json` | Output 4: sandbox record-update proposal. | Needs `requires_human_approval`, `approval_status`, `executed`. |
| `comparison.schema.json` | Output 5: provider comparison. | Providers limited to the 6 canonical names, e.g. `OSRM`. |
| `responsible_role.schema.json` | Output 6: owner and escalation. | Owner ∈ Support L1, Support L2, Account team (Sales), Maps engineering. |
| `next_action.schema.json` | Output 7: recommended next step. | Proposals only; executed-without-approval is rejected by the validator. |

Use case: `copilot/validation/specification_checks/validate_spec.py` loads every `*.schema.json` here (this README is not loaded) and validates each gold envelope; the later runtime will validate its outputs the same way.
