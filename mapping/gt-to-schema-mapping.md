# GT v2.2 to schema mapping

The mapper in `mapping/map_gt.py` reads `/workspace/capstone-trackb/data/gt_v2_2.xlsx` and builds one envelope per record. The GT file is never modified. Approved transforms applied only in the mapped output are: drop `api_probe` (with the 11-record re-label list), and merge `OSRM (OpenStreetMap)` into `OSRM`.

## Field mapping

| Schema output | GT v2.2 source | Rule |
|---------------|----------------|------|
| `record_id`, `intent`, `sub_intent`, `api`, `team`, `bucket`, `split`, `frozen_core` | same-named Data columns (`team` ← `primary_team`) | copied; must already match the controlled vocabulary |
| `tools_expected` | `expected_tools` | split on commas; drop `api_probe`; for the 11 listed ids, use the approved replacement tool list |
| `tools_raw_gt` | `expected_tools` | unmodified tokens, for traceability |
| `response_draft.draft_text` | `reference_answer` | copied verbatim |
| `response_draft.citations` | citations sheet (fallback: `cited_doc_spans`) | one object per span |
| `clarifying_questions` | `gold_clarifying_questions` | one question per bullet line; empty if the cell is blank |
| `qualification_details` | `question` + `api` | conservative regex extraction; `use_case_api.api` is always the record's `api`; missing required fields are listed |
| `proposed_record_update` | `gold_tool_trace` (`update_record` JSON); fallback `reference_answer` | `mode` is `propose`; `executed=false`; `approval_status=pending`; `requires_human_approval=true` |
| `comparison` | `intent`, `bucket`, `service_providers`, citations | applicable for comparison intents/buckets, or pricing/sales records with two or more providers |
| `responsible_role` | `escalation`, `primary_team` | parsed `should_escalate`, `severity`, `owner`, `reason` |
| `next_action` | escalation + tools | `propose_escalation` if escalate; else `propose_record_update` if a gold update exists; else `answer_directly`. Consequential actions stay unexecuted and pending approval |
| `approx_output_tokens` | `reference_answer` | PROPOSED `ceil(chars/4)` |

## Counts

- Records mapped: **521** (eval 418, holdout 103).
- Frozen mapped: **80**.
- Validation pass (all): **521/521**.
- Validation pass (frozen): **80/80**.
- Mapping-time warnings: **0**.

## Artefacts

- `mapping/gold_outputs_all.jsonl`
- `mapping/gold_outputs_frozen.jsonl`
- `mapping/mapping_issues.json`
- `vocab/vocab-diff-gt-v2_2.md`
- `validator/validator-report.md`

