# Task specification: Location Services Sales and Support Copilot

**Document:** C1 task spec, interpretation and qualification  
**Schema version:** 1.0.0  
**Track:** Track-B “Multi-Agent Operations Copilot: An Agentic System Built Entirely on a Hosted ≤8B Inference API”  
**Domain:** Location Services Sales and Support Copilot  
**Status:** Written; pending Shahid’s sign-off (unsigned)  
**GT source of truth (read only):** `/workspace/capstone-trackb/data/gt_v2_2.xlsx` (521 records, sheet `Data`)  
**Inference model (from the Learner Guide):** `Qwen/Qwen3-8B` — combined input and output 8,192 tokens; output 512 tokens by default and 1,024 maximum per call. Embeddings are not provided on the hosted endpoint.

This specification is a design artefact. It does not implement the application. It freezes what the copilot does, what a correct output looks like, when to refuse, and the schemas against which gold and later system outputs are validated.

---

## 1. Purpose and scope

The copilot helps sales and support staff interpret location-services enquiries, qualify them, draft grounded answers, compare documented pricing, capabilities, coverage and limits, propose sandbox record updates, and recommend ownership or escalation.

**Users:** sales and support staff handling customer and prospect enquiries (brief, in-scope).

**APIs in scope:** `directions`, `distance_matrix`, `autocomplete`, `reverse_geocode`.

**Providers the copilot may compare (exactly six):** Google Maps Platform, Ola Maps, Mapbox, OSM Nominatim, OSRM, Mappls (MapmyIndia). The GT label `OSRM (OpenStreetMap)` is merged into `OSRM` (16 records in v2.2; see the v2.3 change list). Comparisons are limited to selected, verifiable sources. Exhaustive coverage of every provider, geography, product, contract price or undocumented capability is out of scope.

**Scenario buckets (10, as in GT v2.2):** qualification, interpretation, docs, history, updates, pricecompare, capabilitycompare, coveragecompare, limitscompare, ownership.

**Out of scope (brief):** dedicated multilingual or multimodal inputs; forward geocoding, place details, nearby search, map rendering, navigation SDKs, geofencing, and fleet or route optimization; live production record writes, real ticket handoffs, sending external messages, autonomous follow-ups and production SLAs; unverified ground truth used as confirmed gold.

---

## 2. Intents

The copilot scores **8 intents**. The original **31 GT labels** are retained as `sub_intent` (an unscored detail label). Intent is separate from the escalation decision: a `human_handoff` record may still have `should_escalate=false` (in v2.2 this occurs for both `billing_dispute` records).

Every v2.2 `sub_intent` value maps to exactly one scored intent. No v2.2 intent or sub_intent label is unmapped or new relative to this table.

| Scored intent | sub_intent labels | v2.2 records |
|---|---|---|
| `pricing_quote` | `pricing_quote`, `pricing_estimate`, `free_tier_question`, `billing_question` | 86 |
| `pricing_comparison` | `pricing_comparison`, `competitive_comparison` | 62 |
| `sales_qualification` | `discovery_qualification`, `capability_fit`, `licensing_fit`, `solution_design` | 30 |
| `capability_match` | `capability_question`, `capability_matching` | 41 |
| `coverage_limits` | `coverage_question`, `limits_question`, `performance_question` | 81 |
| `docs_how_to` | `parameter_question`, `response_fields`, `integration_question`, `migration_question`, `policy_question` | 93 |
| `troubleshooting` | `error_resolution`, `parameter_troubleshooting`, `accuracy_question`, `coverage_error` | 104 |
| `human_handoff` | `production_incident`, `security_incident`, `data_quality`, `accuracy_regression`, `billing_incident`, `contract_request`, `billing_dispute` | 24 |

### 2.1 Required information per intent

The qualification schema always has five required fields — `use_case_api`, `region`, `monthly_volume`, `current_provider`, `timeline` — and three optional fields — `budget`, `technical_constraints`, `decision_maker`. Any of the five that are not stated are listed in `missing_required_fields`. `use_case_api` is an object `{api, use_case}`; `api` is the in-scope API the enquiry is about.

| Intent | Information a complete handling needs | Notes |
|---|---|---|
| `pricing_quote` | All five required qualification fields; currency and the rate source if a conversion is shown | List prices only. No invented contract prices. |
| `pricing_comparison` | All five required fields, used as equivalent requirements across providers | Compare on equal terms; state assumptions. |
| `sales_qualification` | All five required fields; optional fields when offered | Ask for missing required fields rather than inventing them. |
| `capability_match` | `use_case_api`, region, and any stated technical constraints | Answer only documented capabilities. |
| `coverage_limits` | `use_case_api`, region; volume when a limit depends on usage | Use current official limits, not outdated community figures. |
| `docs_how_to` | `use_case_api` and the parameter or workflow being asked about | Cite official parameter names and behaviour. |
| `troubleshooting` | `use_case_api`, the symptom or error, and request context already given | Do not re-ask facts already in history. |
| `human_handoff` | Enough to route: severity, owner, reason, and evidence already provided | Escalation is a proposal pending approval. |

---

## 3. Tools and the approval boundary

The copilot has **four** tools: `doc_search`, `calculator`, `update_record`, `escalate_ticket`. `api_probe` is dropped. There are no provider API keys and no live provider calls. Public documentation may be retrieved; the copilot must not call provider APIs to probe live responses.

`update_record` and `escalate_ticket` are **proposals only**. There are no external sends and no live operations. They write nothing and hand nothing off until a human approves.

**Executable approval boundary**

- Every `proposed_record_update` with `applicable=true` must have `requires_human_approval=true`, `approval_status` in `{pending, approved, rejected}`, and `proposal.mode="propose"`.
- Every `next_action` of type `propose_record_update` or `propose_escalation` must have `requires_human_approval=true`.
- **Validator rule:** reject any output where `executed=true` and `approval_status` is not `approved`. Gold mapped outputs always have `executed=false` and `approval_status=pending` for these actions.

---

## 4. The seven outputs and what a correct answer is

Every copilot turn produces the seven outputs below, wrapped in the versioned envelope (`schemas/envelope.schema.json`, version 1.0.0). Each output has its own versioned JSON Schema. A result is not correct unless it is schema-valid, respects the approval boundary, stays within the step and token limits, and meets the output-specific definition.

### 4.1 Response draft

The customer- or agent-facing reply. Gold text is the GT `reference_answer`.

**Correct when:** it is faithful to the cited official spans; it does not invent prices, coverage, limits or capabilities; it uses conversation history and does not repeat a diagnostic question already answered; where the gold rubric names a metric (for example grounded pricing accuracy or diagnosis correctness), those checks hold; factual claims are cited; refusals use the refusal object rather than a misleading answer.

### 4.2 Clarifying questions

Questions the copilot should ask, or should have answered around, when information is missing.

**Correct when:** the list matches the gold questions in substance (later scored on the frozen set); no question repeats one already asked and answered in history; if nothing needs asking, `needed=false` and the list is empty.

### 4.3 Qualification details

Structured qualification with the required and optional fields above.

**Correct when:** stated facts are copied, not invented; missing required fields are listed; `complete` is true only when all five required fields are filled; the API in `use_case_api` is one of the four in-scope APIs.

### 4.4 Proposed record update

A field-level sandbox diff (`TKT-…` or `OPP-…` in the current gold traces).

**Correct when:** it is a proposal, not an applied write; field values match the gold update when one exists; `requires_human_approval=true`; `executed` remains false until approval; it is `applicable=false` when no update is warranted.

### 4.5 Comparison

A like-for-like comparison of the six allowed providers on pricing, capabilities, coverage and/or limits.

**Correct when:** applicable only where a comparison is in scope; providers are from the six-name list (after the OSRM merge); equivalent requirements and assumptions are stated; figures come from cited sources; undocumented contract prices are refused or flagged, not invented.

### 4.6 Responsible role / owner

`owner`, `team`, `should_escalate`, `severity`, `reason`.

**Correct when:** these match the gold escalation parse; a reason is always present; `should_escalate` is not inferred from intent alone; owner is one of: Support L1, Support L2, Support, Account team (Sales), Maps engineering.

The rare GT owner label `Support` (2 records) is kept as in v2.2. It is not merged into Support L1 or L2.

### 4.7 Next action

One of: `answer_directly`, `ask_clarifying_questions`, `propose_record_update`, `propose_escalation`, `refuse`.

**Correct when:** escalations and record updates are proposals pending approval; a refusal uses `refuse` together with the draft refusal object; otherwise the action matches the gold routing (escalate if `should_escalate` or `escalate_ticket` is expected; else propose an update if one is expected; else answer directly).

---

## 5. Refusal and unsupported-answer policy

The copilot must refuse, or answer only with a clearly marked limitation, in these cases. A refusal is a schema-valid draft with `is_refusal=true` and a `refusal.policy_id` from the list below. It must not invent a substitute fact to avoid refusing.

| Policy id | When it applies | Behaviour |
|---|---|---|
| `out_of_scope_api` | Forward geocoding, place details, nearby search, map rendering, navigation SDKs, geofencing, fleet or route optimization, or any API outside the four in scope | Refuse the out-of-scope part; if an in-scope API is also asked, answer only that part. |
| `out_of_scope_modality` | Voice, images, or other multimodal input; dedicated multilingual or code-switched benchmarking | Refuse. |
| `undocumented_fact` | A price, limit, coverage claim or capability not supported by a retrieved official span | Do not invent. Say it is undocumented and cite what is known. |
| `contract_or_unpublished_price` | A request for a contract, committed, or unpublished price | Refuse to quote one. Route to the Account team as a proposal if a commercial handoff is warranted. |
| `live_operations` | A request to apply a production write, send an external message, or perform a real ticket handoff | Refuse to execute. A sandbox proposal may be offered, held for approval. |
| `unsafe_or_injection` | Requests to ignore instructions, leak the system prompt or keys, run unregistered tools, or otherwise attack the agent | Refuse. No tool call to unregistered tools. Never echo `TRACKB_API_KEY` or other secrets. |
| `off_topic` | Enquiries unrelated to the location-services sales and support task | Refuse and state the scope. |
| `unverified_source` | The only source is an outdated or unofficial claim that official docs contradict | Prefer official docs; mark the unofficial claim as outdated. Do not present it as current fact. |

In-scope, documented questions must not be refused. False-refusal tests belong to a later safety activity; the rule here is: if the enquiry is in scope and the docs support an answer, answer it.

---

## 6. Planner, executor and critic (application roles)

These are application roles for the later planner→executor→critic loop, not code in this activity. The loop may use at most 10 steps per query (Track-B cap and brief).

**Planner.** Interprets the user turn and history into intent, sub_intent, API, team and a qualification object (including missing required fields). Selects a bounded sequence of registered tools. Must not plan a live provider API call, an unregistered tool, or an executed write or send. Must stop planning at or before 10 steps.

**Executor.** Runs only the four registered tools, with typed inputs. `calculator` does deterministic arithmetic; the model must not substitute its own math for the tool. `update_record` and `escalate_ticket` emit proposals only (`mode=propose`, `executed=false`) and never send externally. `doc_search` retrieves corpus spans with source metadata.

**Critic.** Checks schema validity, citation grounding, qualification completeness, approval flags, step count and the output-token budget. It rejects outdated community claims that official docs contradict, and sends failures back to the planner or executor with a reason. A run is not finished while the critic’s last verdict is a failure, except when the step limit is reached, in which case the system must terminate with an escalated or refused output rather than looping.

---

## 7. Citation and traceability

- Every factual claim in a draft (prices, limits, coverage, parameter behaviour, policy) must be supported by at least one citation `{url, span, supports_claim}`.
- Spans are marked `verbatim` or `summary` when that distinction is known, matching the GT citations sheet.
- Do not invent URLs or quote text that was not retrieved.
- Each run must be traceable to a record id (when scoring), the tools actually proposed or called, the citations used, and — in later activities — a trace in LangSmith, Langfuse or OpenTelemetry. This spec only requires the fields that the envelope already stores.
- Unvalidated or unresolved records do not count as confirmed gold (brief). All 521 v2.2 records currently have `review_status=pending`.

---

## 8. Privacy, minimisation and human approval

- Collect only the qualification fields defined here. Do not solicit extra personal data.
- Do not store or echo API keys, tokens, or other secrets. Request URLs in clarifying questions must have keys removed, as the gold questions already require.
- PII detection and redaction in logs and traces is a later responsible-AI activity; this spec requires that secrets and raw credentials never appear in drafts, tool arguments, or stored gold outputs.
- Consequential actions (`update_record`, `escalate_ticket`) stay in the sandbox and take effect only after recorded human approval (reviewer, timestamp, decision, final diff). That boundary is enforced by the schemas and the validator rule in section 3.

---

## 9. Step limit and token budget

- **Step limit:** at most 10 steps per query (Track-B guardrail; brief component 10). The envelope records `step_count_limit=10`.
- **Output token budget:** at most 1,024 tokens per model call (Learner Guide maximum). The envelope records `output_token_budget=1024`. The default output length on the endpoint is 512 tokens; callers may raise `max_tokens` up to 1,024.
- **Combined context:** input plus output must stay within 8,192 tokens (Learner Guide).
- **Token counting (PROPOSED approximation):** no Qwen/Qwen3-8B tokenizer is available offline, and the hosted endpoint is not called from this activity. The validator uses `ceil(Unicode character count / 4)` on `response_draft.draft_text` and flags this as a proposed approximation. Official counts are those returned by the endpoint `usage` field. Under that approximation, all 521 mapped drafts are at or below 408 tokens, and all 80 frozen drafts are at or below 408 tokens, so none exceed 1,024.

---

## 10. Reviewer policy and sign-off

**Decision applied:** Shahid signs off this specification and reviews gold records alone.

**Single-reviewer policy for the 244 `needs_two_reviewers=true` flags (explicitly resolved, not ignored):**

1. In a later GT v2.3, retire the boolean `needs_two_reviewers`.
2. Replace it with `review_priority`: `high` or `standard`. Records that are `needs_two_reviewers=true` in v2.2 (244 records; 45 of them frozen) become `high`. That flag was defined in v2.2 attribute details as: pricing, billing/contract, policy/licensing and escalation/ownership items, or any answer that states a price.
3. Every `high` record requires a **mandatory second-pass self-review by Shahid**, with recorded evidence, in addition to the first pass. Evidence includes: prices and limits checked against the cited official span; escalation decision, owner and severity checked against the rules; policy or licensing claims checked against the cited policy page; a short note of what was checked and the outcome.
4. Both passes are logged (reviewer, timestamp, pass number, evidence pointer, decision). `review_status` stays `pending` until the required passes are complete.
5. `standard` records require a single recorded review by Shahid.
6. No record is treated as confirmed gold until its required review passes are complete (brief: unvalidated records do not count as confirmed gold).

This policy conflicts with the row 3 acceptance-criterion wording that “all 6 team members have reviewed” the spec. That wording is not silently treated as satisfied. Shahid’s decision is the reviewer policy for this project; the six-member review is recorded as an open acceptance-criterion conflict in `review-log.md` and in the delivery report.

### Sign-off (unsigned)

| Role | Name | Decision | Date (Asia/Calcutta) | Signature |
|---|---|---|---|---|
| Spec owner and sole reviewer | Shahid Kamal | Pending | | |

---

## 11. Thresholds

Thresholds used by this activity are only those that row 3, Track-B, the brief, or the Learner Guide already define. Any figure chosen here for later work is marked **PROPOSED**.

| Threshold | Value | Status | Source |
|---|---|---|---|
| Frozen gold expected outputs that validate | 100% of frozen records, 0 schema errors | Defined | Activities row 3 acceptance criteria |
| Each of the 7 outputs has a versioned JSON Schema | Required | Defined | Activities row 3 acceptance criteria |
| Spec committed in git | Required | Defined | Activities row 3 acceptance criteria |
| All 6 team members have reviewed the spec | As written in row 3 | **Conflict** | Superseded for this project by Shahid’s single-reviewer decision; not marked passed |
| Frozen eval set size | 60–100 queries | Defined | Track-B Week 1; activities row 1 |
| Agent steps per query | ≤ 10 | Defined | Track-B guardrail; brief component 10 |
| Output tokens per model call | ≤ 1,024 (default 512) | Defined | Learner Guide |
| Combined input and output tokens | ≤ 8,192 | Defined | Learner Guide |
| Tokeniser used by the validator | `ceil(chars / 4)` on the draft text | **PROPOSED** | Chosen because no Qwen tokenizer is available offline; official counts are the endpoint `usage` field |
| Target frozen balance | about 10 per intent (at least 8), 60–100 records, balanced on bucket, API and team as far as possible, `verified_live` only | Defined as a target by Shahid’s decision and Track-B | Feasibility against v2.2 is reported in section 12; the set is not re-picked in this activity |

Later-row scoring thresholds (for example intent accuracy ≥ 90% in row 4, Cohen’s κ ≥ 0.70 in row 5, each bucket ≥ 5 in row 6) are not adopted or altered here. They remain as written in the activities file, subject to the row 1 note that numbers not fixed by Track-B are proposed targets for the team to confirm.

---

## 12. Frozen eval set (feasibility on v2.2; not re-picked)

Track-B requires an evaluation set of 60–100 realistic queries with gold answers, written before any agent code. Shahid’s rule for this project: frozen records must be `verified_live` only; target 60–100 records at about 10 per intent (at least 8), balanced on bucket, API and team as far as possible. This activity does not edit the GT and does not re-pick the frozen set.

**v2.2 already meets the verified_live-only rule and the intent, API and team targets:**

- 80 records have `frozen_core=True`. All 80 are `split=eval` and all 80 are `verification_status=verified_live`. Count of frozen records that are not `verified_live`: **0**.
- Frozen count per scored intent: **10 each**.
- Frozen count per API: **20 each** (25%, above a 15% floor used in later row 6 wording).
- Frozen team split: Sales **43**, Support **37** (53.75% / 46.25%, inside a 40–60% band).
- `verified_live` records in the eval split, per intent, available as a pool: coverage_limits 59, pricing_quote 35, pricing_comparison 30, docs_how_to 29, troubleshooting 17, capability_match 17, sales_qualification 16, human_handoff 10. Each intent has at least 10 verified_live eval records, so 10 per intent is feasible (and already achieved).

**Bucket balance is not met and cannot be met under the verified_live-only rule without new live verification:**

| Bucket | Frozen in v2.2 | `verified_live` eval records |
|---|---|---|
| updates | 21 | 29 |
| qualification | 16 | 32 |
| limitscompare | 12 | 36 |
| ownership | 11 | 11 |
| capabilitycompare | 11 | 27 |
| pricecompare | 5 | 24 |
| history | 3 | 13 |
| interpretation | 1 | 1 |
| coveragecompare | 0 | 40 |
| docs | 0 | 0 |

The `docs` bucket has 50 records, all `docs_how_to`, and **zero** `verified_live` records (47 `carried_from_v1_unverified`, 3 `flagged`). The `interpretation` bucket has only **one** `verified_live` eval record. A frozen set with at least 5 records in every bucket (the later row 6 wording) is therefore not feasible on v2.2 if membership is restricted to `verified_live`. No alternative frozen-id list is proposed that would claim otherwise.

**Recommendation:** keep the current 80 frozen ids. No membership change is required for the verified_live-only rule or for intent balance. Optional later work, for a subsequent GT version and not done here, is to live-verify additional `docs` and `interpretation` records if bucket balance is required.

Two content changes will touch frozen records when v2.3 is applied, without changing membership: `GT-LBS-RG-001` (the one frozen `api_probe` record) and three frozen OSRM label merges (`GT-LBS-DIR-221`, `GT-LBS-DM-218`, `GT-LBS-DM-224`). Those are listed in the change list.

---

## 13. Schemas, vocabulary, mapping and validator

- Versioned JSON Schemas (all `x-spec-version: 1.0.0`) live in `schemas/`: one file for each of the seven outputs, plus `envelope.schema.json`.
- The controlled vocabulary is `vocab/controlled-vocabulary.json`. The read-only diff against distinct GT v2.2 values is `vocab/vocab-diff-gt-v2_2.md`.
- The mechanical mapper `mapping/map_gt.py` maps all 521 records and writes `mapping/gold_outputs_all.jsonl` and `mapping/gold_outputs_frozen.jsonl`. It applies the approved `api_probe` drop and the OSRM merge only in the mapped output. The GT file is not modified. Raw `expected_tools` tokens are preserved in `tools_raw_gt`.
- The validator `validator/validate_spec.py` checks: schema self-consistency; every mapped envelope and nested output; the approval rule; qualification required-field consistency; and the (proposed) token budget. Run it from the repo root with `repo/.venv/bin/python validator/validate_spec.py`. The report is `validator/validator-report.md`.

---

## 14. GT change list for v2.3

Proposed GT changes are recorded in `gt-change-list-v2_3.md` for later application by the Knowledge & Validation Engineer. This activity does not edit any GT file. The list covers: the 11 `api_probe` re-labels (with the one frozen record flagged); the 16 `OSRM (OpenStreetMap)` → `OSRM` merges; the `needs_two_reviewers` policy change; and the frozen-core feasibility finding (no membership change).

---

## 15. Sources

- Activities file, row 3 activity text and acceptance criteria (verbatim criteria for this deliverable).
- Project brief, including lines 14, 21, 25, 26, 31, 35, 38, 45 and 46.
- Capstone-Templates-GenAI-Agentic-AI.pdf, Track-B section (spec + 60–100 gold queries; planner→executor→critic; ≤10 steps; human-in-the-loop for consequential actions).
- Track B inference API guide (Learner Guide), 5 November 2026.
- GT v2.2 workbook, including the Data, citations, attribute details, data-usage, summary and stats sheets.
- Shahid’s final decisions for this activity, applied as written.
