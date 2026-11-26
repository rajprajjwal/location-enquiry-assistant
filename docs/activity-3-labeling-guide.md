# Activity 3 labeling guide

Version 0.2.0

Use this guide and the [gold-record schema](../contracts/evaluation/gold_record.schema.json) to label the customer's current request in context. Read the conversation up to that turn. Choose labels from the [task specification](../spec/spec.md) and apply the evidence boundaries in the [qualification mapping rules](../mapping/gt-to-schema-mapping.md).

## Classifying the request

Choose one primary intent based on the answer or action the customer needs most. Use the closest sub-intent listed under that intent in the task specification.

| Intent | Decision rule | Short example |
|---|---|---|
| `pricing_quote` | Estimate a price for one specified provider or plan. | “What will our monthly usage cost with Provider A?” |
| `pricing_comparison` | Compare costs across options on the same basis. | “What would each provider charge for the same monthly volume?” |
| `sales_qualification` | Gather requirements to decide product fit or licensing. | “What details do you need to recommend a service for us?” |
| `capability_match` | Determine whether a feature is supported. | “Can the response include a separate duration for each leg?” |
| `coverage_limits` | Determine geographic coverage, a quota, a request cap or a documented performance limit. | “How many waypoints can I submit?” |
| `docs_how_to` | Explain a documented parameter, workflow, integration step or usage policy. | “Which field do I set to change the response language?” |
| `troubleshooting` | Diagnose an observed failure or incorrect result. | “The request started returning an error after we changed this parameter.” |
| `human_handoff` | The appropriate resolution involves a person or team, such as a contract request, dispute or production incident. | “Can someone quote a committed annual price?” |

Read what the customer wants resolved. A question about a documented cap can be `coverage_limits` when it asks only for that cap, even if the case mentions an error. Identify `api` from the operation the customer is asking about and use one of `directions`, `distance_matrix`, `autocomplete`, or `reverse_geocode`. Use `Sales` for buying, quoting and product-fit questions. Use `Support` for help with an existing integration or service issue. Record uncertainty in the pilot rationale and choose the best supported label.

## Field rules and worked example

The worked case, `GT-LBS-DIR-011`, asks which Directions APIs the customer's two-wheeler rental business could use for six million requests a month in India and what each would cost. The table shows how to label each field. Longer evidence fields below are abbreviated for readability.

| Field | What to record | Worked example |
|---|---|---|
| `record_id` | Preserve the stable identifier. Match it in the input and expected-output files. | `GT-LBS-DIR-011` in both places. |
| `split` | Preserve the assigned dataset partition. | `eval`. |
| `frozen_core` | Preserve whether the case belongs to the frozen evaluation set. | `true`. |
| `bucket` | Preserve the scenario bucket used to balance evaluation coverage. | `pricecompare`. |
| `input` | Keep the current query, earlier turns in order, and only facts available before this turn. | The Directions enquiry is the query. History and known facts are empty lists. |
| `expected_interpretation` | Record intent, sub-intent, API, team and qualification. List missing required fields after accounting for facts supplied in the query or earlier turns. | `pricing_comparison` for both intent and sub-intent, `directions`, `Sales`, India, a two-wheeler rental use case and 6 million requests/month. Current provider and timeline are missing, so `complete` is false. |
| `context` | Capture the evidence needed to understand the expected response. Keep it separate from the customer input. | Official pricing and billing evidence for the Directions services being compared. |
| `reference_answer` | Write what a correct, useful reply should cover and state any assumptions that affect the conclusion. | Compare providers at the same 6 million requests/month and show how the billing tiers produce each total. |
| `cited_doc_spans` | For each claim requiring support, identify the source URL and the passage or summary that supports it. | Use the Directions pricing section of Ola Maps' pricing page to support the Ola calculation. [Source](https://maps.olakrutrim.com/pricing/details) |
| `rubric` | State observable checks a reviewer can apply to an answer. | Check that the Ola, Google and Mapbox totals follow from the stated tier arithmetic. |
| `gold_clarifying_questions` | Record relevant questions whose answers are absent from the conversation. Use an empty list when none is needed. | Ask whether they need live-traffic ETAs or whether static routes are sufficient. |
| `escalation` | Record owner, team, severity, whether to escalate now, and why. Judge the action on the case evidence. | Account team (Sales), `SEV4`, `should_escalate=false` for the standard quote in the case. Document any conditions for a later handoff in the reason. |
| `expected_tools` | List only the tools needed to support the expected response and action. | `doc_search` and `calculator`. |
| `gold_tool_trace` | Record the expected sequence, key arguments and observable result. Use null if there are no tool calls. | Search for the published Directions rate tiers, then calculate the total from the volume and each applicable tier. |

The qualification object has five required fields. Use the stated API and use case under `use_case_api`. Preserve region, monthly volume and its unit, current provider, and timeline where supported. Use null for missing values and recompute `missing_required_fields`. Optional budget, technical constraints, and decision maker remain null when absent. Preserve explicit values from earlier user turns and record the actual unit, such as requests or matrix elements.

## Pricing, policy and escalation

- **Pricing.** Use published rates and billable units. Compare providers using equivalent workloads and describe tiering, free allowances, currency, conversions, and assumptions where relevant. For an unpublished price, record the limit of available evidence and the appropriate account-team action.
- **Policy.** Cite the official documentation that supports each restriction or allowance. Scope the answer to the documented API, version, and usage scenario. A claim that remains unresolved belongs in the review notes before sign-off.
- **Escalation and tools.** Record the appropriate owner and severity separately from intent. Describe record updates and escalations as sandbox proposals requiring human approval. Evidence retrieval and calculations can be represented in the trace as expected sandbox actions.

## Pilot

Give both annotators this guide, the [10 pilot enquiries](../eval/activity-3-pilot/cases.md), the [blank annotation template](../eval/activity-3-pilot/annotations.template.csv), and the [two completed examples](../eval/activity-3-pilot/annotations.examples.csv). Annotators should not have seen the pilot labels. The examples illustrate the format using cases outside the 10 pilot enquiries.

### Completed examples

| Example | Enquiry | Labels | What to notice |
|---|---|---|---|
| `EX01` | A two-wheeler rental business asks which Directions providers it can use and what each would cost for six million requests a month in India. | `pricing_comparison`, `directions`, `Sales` | The volume, unit, region and use case are stated. Current provider and timeline are missing. The completed row shows price evidence, a calculation trace and follow-up questions. |
| `EX02` | An integration gets region and country from reverse geocoding even though it expected a street address. | `troubleshooting`, `reverse_geocode`, `Support` | An observed result drives the intent. The completed row records the parameter guidance, the supporting citation, the rubric and the Support L1 decision. An empty clarification list is recorded as `[]`. |

### How to fill each column

The first six columns come from the case packet. Keep those values as provided. The coordinator maps each `pilot_id` to the gold record's `record_id` after submission.

| Template column | What to enter |
|---|---|
| `pilot_id` | Prefilled case ID such as `P01`. Use the same ID when referring to a case. |
| `split`, `frozen_core` | Prefilled as `eval` and `true` for this pilot. |
| `query` | Prefilled latest user message. Keep it as supplied in the case packet. |
| `history` | Prefilled earlier user and assistant messages in order. `[]` means there are no earlier messages. |
| `known_facts` | Prefilled facts supplied before the current turn. `[]` means no stored facts were supplied. |
| `intent` | **Required.** Choose one of `pricing_quote`, `pricing_comparison`, `sales_qualification`, `capability_match`, `coverage_limits`, `docs_how_to`, `troubleshooting`, or `human_handoff`. |
| `api` | **Required.** Choose one of `directions`, `distance_matrix`, `autocomplete`, or `reverse_geocode`. |
| `team` | **Required.** Choose `Sales` or `Support`. |
| `sub_intent` | Choose one from the [sub-intent options](#sub-intent-options) for your selected intent. You can leave it blank for the agreement pilot. |
| `bucket` | Choose one of `qualification`, `interpretation`, `docs`, `history`, `updates`, `pricecompare`, `capabilitycompare`, `coveragecompare`, `limitscompare`, or `ownership`. |
| `use_case`, `region` | Capture the customer's stated use case and relevant region. The `api` column also supplies the API part of `use_case_api`. |
| `monthly_volume_raw`, `monthly_volume_value` | Enter the customer's phrase and the normalized numeric amount. Leave an unknown value blank. |
| `monthly_volume_unit` | Choose `requests_per_month`, `calls_per_month`, `lookups_per_month`, `sessions_per_month`, `elements_per_month`, `searches_per_month`, `queries_per_month`, or `transactions_per_month` based on the phrase. Use `per_month` when a monthly amount is stated without a unit. Leave blank if no monthly volume is stated. |
| `current_provider` | If current use is supported, choose `Google Maps Platform`, `Ola Maps`, `Mapbox`, `OSM Nominatim`, `OSRM`, or `Mappls (MapmyIndia)`. Otherwise leave blank. |
| `timeline` | Enter the stated timeline as free text or leave it blank. |
| `budget`, `technical_constraints`, `decision_maker` | Enter clearly stated optional qualification details. Leave an unstated field blank. |
| `missing_required_fields` | Select all missing fields from `use_case_api`, `region`, `monthly_volume`, `current_provider`, and `timeline`. Separate them with commas. Enter `[]` when none are missing. |
| `complete` | Enter `true` when all required qualification fields are filled and `false` when one or more are missing. |
| `context` | Summarize the evidence relevant to answering the enquiry. |
| `reference_answer` | Write the expected answer with any assumptions or limitations that materially affect it. |
| `cited_doc_spans` | Add one line per supporting passage with the source URL, passage or summary, and supported claim. The example rows show the existing format. |
| `rubric` | List specific checks the reviewer should apply to the answer and any expected actions. |
| `gold_clarifying_questions` | Enter one expected follow-up per line. Use `[]` when no follow-up is needed. |
| `should_escalate` | Enter `true` or `false` based on whether escalation is needed now. |
| `owner` | Choose `Support L1`, `Support L2`, `Account team (Sales)`, or `Maps engineering`. |
| `severity` | Choose `SEV1`, `SEV2`, `SEV3`, or `SEV4`. |
| `escalation_reason` | Explain the escalation decision in free text. |
| `expected_tools` | Select from `doc_search`, `calculator`, `update_record`, and `escalate_ticket`. Separate multiple tools with commas. Enter `[]` if none are needed. |
| `gold_tool_trace` | Record one expected sandbox call per line with its purpose and observable outcome. Leave blank if no tools are expected. |
| `rationale` | Briefly explain any uncertain or borderline label. This note is for adjudication. |

### History and qualification example

In the pilot, you **read** `query`, `history`, and `known_facts` as supplied. `history` contains the earlier conversation messages, including earlier assistant questions. For a brand-new gold record, put earlier turns in oldest-first order in `history` and put the latest user message in `query`. Use `[]` if the enquiry has no earlier turns.

**Qualification** is the group of columns that captures the customer's stated requirements. There is no separate `qualification` cell. Use facts the customer supplied in the current query or an earlier turn, plus any supplied known facts. A later explicit correction takes precedence. Leave unknown qualification cells blank. A suggestion made only by the assistant is insufficient evidence for a qualification value.

Here is a practice example outside the pilot.

> **Earlier user:** We use Mapbox in India to compare travel times between depots.  
> **Earlier assistant:** What is your monthly volume, and when do you need to go live?  
> **Current query:** For Distance Matrix we expect 50,000 elements per month. We haven't chosen a launch date.

| Qualification column | Value to enter |
|---|---|
| `api` and `use_case` | `distance_matrix` and `compare travel times between depots`. Together they form `use_case_api`. |
| `region` and `current_provider` | `India` and `Mapbox`. The earlier user message already states both. |
| `monthly_volume_raw` | `50,000 elements per month` |
| `monthly_volume_value` | `50000` |
| `monthly_volume_unit` | `elements_per_month` |
| `timeline` | Leave blank. The customer has not chosen a date. |
| `budget`, `technical_constraints`, and `decision_maker` | Leave blank. These fields are optional. |
| `missing_required_fields` | `timeline` |
| `complete` | `false` |

For `missing_required_fields`, count `use_case_api` as present once the API is identified. The free-text `use_case` can still be blank when the customer has not stated one. Only the five required fields affect `complete`.

### Sub-intent options

| Selected intent | What to enter in `sub_intent` |
|---|---|
| `pricing_quote` | `pricing_quote`, `pricing_estimate`, `free_tier_question`, `billing_question` |
| `pricing_comparison` | `pricing_comparison`, `competitive_comparison` |
| `sales_qualification` | `discovery_qualification`, `capability_fit`, `licensing_fit`, `solution_design` |
| `capability_match` | `capability_question`, `capability_matching` |
| `coverage_limits` | `coverage_question`, `limits_question`, `performance_question` |
| `docs_how_to` | `parameter_question`, `response_fields`, `integration_question`, `migration_question`, `policy_question` |
| `troubleshooting` | `error_resolution`, `parameter_troubleshooting`, `accuracy_question`, `coverage_error` |
| `human_handoff` | `production_incident`, `security_incident`, `data_quality`, `accuracy_regression`, `billing_incident`, `contract_request`, `billing_dispute` |

### Submission

Collect both annotators' independently completed intent, API, and team labels before revealing or discussing answers. The remaining editable fields can also be filled for full gold-record review. They are retained for qualitative review.

Measure Cohen’s κ separately for intent, API, and team on the 10 independent pairs. The target is κ ≥ 0.70 per field. If a field falls below the target, revise the rule that caused the disagreements and repeat the pilot. If κ is undefined because both annotators used the same single category throughout, revise the case mix for that field and repeat. Keep the original submissions and record the final adjudication separately.

Once both submissions are ready, run the scorer from the Git checkout.

```bash
python3 eval/score_activity3_pilot.py annotator-a.csv annotator-b.csv
```

## Completed pilot agreement

The supplied two-annotator pilot has been scored for intent, API and team. All three agreement targets pass. Original submissions, formatting-only scoring exports and unresolved decisions are preserved in the [agreement report](../eval/activity-3-pilot/results/annotation-agreement/report.md). Record consensus decisions separately in the adjudication template before promoting final labels.
