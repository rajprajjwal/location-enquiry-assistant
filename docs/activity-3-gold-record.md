# Activity 3 gold-record schema

The [GoldRecord v0.1.0](../contracts/evaluation/gold_record.schema.json) contract defines the complete record reviewers work with. The committed [80-case handoff](../eval/frozen-interpretation/) provides the input, expected interpretation and answer evidence. Match the CSV `id` with `record_id` in the JSONL files.

| Gold-record field | Source in the 80-case handoff | Meaning |
|---|---|---|
| `record_id`, `split`, `frozen_core`, `bucket` | `ground-truth-frozen.csv` | Stable case ID and dataset membership. A frozen case belongs to the eval split. Its frozen status records membership. |
| `input` | `inputs.jsonl` | Latest customer query, ordered prior turns, and any facts available before the current turn. An empty list represents no history or known facts. |
| `expected_interpretation` | `gold.jsonl` and the CSV `sub_intent` | Expected intent, sub-intent, API, team and qualification details. The qualification object includes missing required fields and completion. |
| `context` | CSV `context` | Background evidence that helps the reviewer understand the expected response. |
| `reference_answer` | CSV `reference_answer` | The expected response to the enquiry. |
| `cited_doc_spans` | CSV `cited_doc_spans` | Source URL, supporting passage or summary, and the specific claim it supports. These can be read with the existing GT citation parser. |
| `rubric` | CSV `rubric` | Scoring criteria and any phase checks, preserved as reviewer-authored text. |
| `gold_clarifying_questions` | CSV `gold_clarifying_questions` | Expected follow-up questions. A blank cell becomes `needed: false` with an empty question list. |
| `escalation` | CSV `escalation` and `primary_team` | Expected owner, team, severity, escalation decision and reason. |
| `expected_tools` | CSV `expected_tools` | List of expected tool names. |
| `gold_tool_trace` | CSV `gold_tool_trace` | Ordered expectations for sandbox calls and outcomes, preserved as text. The value is null when no tools are expected. |

When using this contract, check that the outer and input record IDs match, the selected sub-intent belongs to the intent, and qualification's `use_case_api.api` matches the labeled API. Check that the missing-field list matches the null required fields. These are cross-field checks alongside shape validation.

## Worked case

`GT-LBS-DIR-011` asks for a provider and price comparison for six million monthly Directions requests in India. Its expected interpretation is `pricing_comparison`, `directions` and `Sales`. The expected qualification marks current provider and timeline as missing. The case has a reference answer and claim-level citations. Its expected tools are `doc_search` and `calculator`. One rubric criterion checks whether the provider totals match the arithmetic.

## How Activity 2 uses the record

Activity 2 receives `input`. Its scorer checks predicted intent, API, team, qualification and missing fields against the saved interpretation gold. Reference answers, cited spans, rubric and tool expectations support downstream evaluation. `predictions.jsonl` stores model results separately.

The [Activity 3 labeling guide](activity-3-labeling-guide.md) and [10-case pilot packet](../eval/activity-3-pilot/) are ready for independent annotation. Schema validation checks record structure. Reviewer agreement, evidence correctness and formal sign-off require their own checks.
