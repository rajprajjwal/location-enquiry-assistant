# GT change list for v2.3

**Status:** Proposed only. Do not apply in this activity.  
**Apply later by:** Knowledge & Validation Engineer.  
**Base file:** `/workspace/capstone-trackb/data/gt_v2_2.xlsx` (read only here; SHA-256 `2e3f3a2ff84144ff8444aa850e493629fec6ec0a45adc9678fb374ee46d900fe` at the time this list was written).  
**v2.2 stays untouched** until a later, approved v2.3 build.

This list is derived from the Data sheet of GT v2.2 and from Shahid’s approved decisions. Judgements for tool re-labels use each record’s `question`, `gold_tool_trace` and `reference_answer`.

---

## (a) Re-label the 11 `api_probe` records

`api_probe` is dropped from the copilot. There are no provider API keys and no live provider calls. Each row keeps every tool other than `api_probe`. The proposed `expected_tools` value is the remaining registered tools, in the order `doc_search`, `calculator`, `update_record`, `escalate_ticket`.

**Flag:** `GT-LBS-RG-001` is the only frozen (`frozen_core=True`) record in this set. It is also `verified_live` and in the eval split. Changing its `expected_tools` is a frozen gold-content change, not a membership change.

| id | split | frozen_core | current expected_tools | proposed expected_tools | Why |
|---|---|---|---|---|---|
| GT-LBS-DIR-002 | holdout | False | doc_search, api_probe, update_record | doc_search, update_record | The gold diagnosis is documented: `duration_in_traffic` needs driving plus a non-past `departure_time`. The probe (call with `departure_time=now`) only confirms the docs. The sandbox ticket update remains. |
| GT-LBS-DIR-004 | holdout | False | doc_search, api_probe | doc_search | The answer classifies the 422 / “No serviceable boundary” as documented out-of-coverage, not a bug. The Pune control probe is not required once the official reason is applied. |
| GT-LBS-DIR-042 | holdout | False | doc_search, api_probe | doc_search | Same coverage-error pattern for a Siliguri→Kathmandu request. The gold answer is from the Ola spec. (The v2.2 trace lists only `api_probe`, while `expected_tools` also lists `doc_search`; the proposal keeps `doc_search`.) |
| GT-LBS-DIR-064 | eval | False | doc_search, api_probe | doc_search | The root cause is the documented `lat,lng` origin order. The probe only demonstrates the swapped-origin fix. |
| GT-LBS-DIR-083 | holdout | False | doc_search, api_probe, escalate_ticket | doc_search, escalate_ticket | Production regression on in-India coordinates. Official docs distinguish a server-side 500 from out-of-coverage. `escalate_ticket` stays, as a proposal. A live reproduce call is out of scope. |
| GT-LBS-DM-004 | eval | False | doc_search, api_probe | doc_search | The gold answer uses documented element-status vs top-level quota statuses. The probe (“negate longitude”) is illustrative, not required for the cited diagnosis. |
| GT-LBS-DM-084 | holdout | False | api_probe, escalate_ticket | escalate_ticket | Production 5xx outage. The gold path is evidence collection and escalation. A live probe is out of scope. |
| GT-LBS-AC-004 | holdout | False | doc_search, api_probe | doc_search | The answer is the documented `components=country:in` restriction. The probe only illustrates that restriction. |
| GT-LBS-AC-087 | holdout | False | api_probe, escalate_ticket | escalate_ticket | Production empty predictions even for “Bengaluru”. The gold path is to treat this as a service-side incident and escalate. A live probe is out of scope. |
| **GT-LBS-RG-001** | eval | **True** | doc_search, api_probe | doc_search | **FROZEN.** The gold answer explains documented post-filter `ZERO_RESULTS` for `result_type` and `REQUEST_DENIED` when filters are sent without a key. The probe (widen `result_type`) is a demonstration, not needed for the cited diagnosis. |
| GT-LBS-RG-085 | eval | False | api_probe, escalate_ticket | escalate_ticket | Systematic wrong localities in production. The gold path is to collect evidence and escalate. A live probe is out of scope. |

Counts: 11 records (4 eval, 7 holdout); 1 frozen.

After this change, also update any `gold_tool_trace` steps that call `api_probe` so the gold trace matches the new `expected_tools`. Do not invent replacement live calls.

---

## (b) Merge `OSRM (OpenStreetMap)` into `OSRM`

Canonical provider label: `OSRM`. Apply in `service_providers` and in any other cell that uses the long form (for example an `update_record` field). Do not collapse distinct providers. `OSRM` and `OSM Nominatim` stay separate.

**16 records** in v2.2 contain the label `OSRM (OpenStreetMap)`:

| id | split | frozen_core | current service_providers (relevant part) |
|---|---|---|---|
| GT-LBS-DIR-201 | eval | False | …, OSRM (OpenStreetMap) |
| GT-LBS-DIR-202 | eval | False | …, OSRM (OpenStreetMap) |
| GT-LBS-DIR-203 | eval | False | …, OSRM (OpenStreetMap) |
| GT-LBS-DIR-204 | eval | False | …, OSRM (OpenStreetMap) |
| GT-LBS-DIR-207 | eval | False | …, OSRM (OpenStreetMap), … |
| GT-LBS-DIR-208 | eval | False | …, OSRM (OpenStreetMap), … |
| GT-LBS-DIR-211 | eval | False | …, OSRM (OpenStreetMap) |
| GT-LBS-DIR-212 | eval | False | …, OSRM (OpenStreetMap) |
| GT-LBS-DIR-215 | eval | False | OSRM (OpenStreetMap) |
| GT-LBS-DIR-221 | eval | **True** | Ola Maps, OSRM (OpenStreetMap) |
| GT-LBS-DM-209 | eval | False | …, OSRM (OpenStreetMap), … |
| GT-LBS-DM-210 | eval | False | …, OSRM (OpenStreetMap) |
| GT-LBS-DM-211 | eval | False | OSRM (OpenStreetMap) |
| GT-LBS-DM-212 | eval | False | OSRM (OpenStreetMap) |
| GT-LBS-DM-218 | eval | **True** | OSRM (OpenStreetMap) |
| GT-LBS-DM-224 | eval | **True** | OSRM (OpenStreetMap) |

Three of these are frozen: `GT-LBS-DIR-221`, `GT-LBS-DM-218`, `GT-LBS-DM-224`. This is a label merge only.

---

## (c) Retire `needs_two_reviewers` and replace it with a single-reviewer policy

Shahid reviews alone. The 244 `needs_two_reviewers=true` flags (45 of them frozen) must not be ignored. All 521 records currently have `review_status=pending`.

Proposed v2.3 field changes:

1. Remove `needs_two_reviewers`.
2. Add `review_priority` with values `high` and `standard`.
3. Set `review_priority=high` on the 244 records that are `needs_two_reviewers=true` in v2.2. Those records were defined in the v2.2 attribute-details sheet as pricing, billing/contract, policy/licensing and escalation/ownership items, or any answer that states a price. All other records are `standard`.
4. Policy (also stated in `spec/spec.md` and `review-log.md`):
   - `high`: mandatory second-pass self-review by Shahid, with recorded evidence, in addition to the first pass.
   - `standard`: a single recorded review by Shahid.
   - Evidence for a `high` second pass: prices and limits checked against the cited official span; escalation decision, owner and severity checked; policy or licensing claims checked; a short note of what was checked and the outcome.
   - Both passes are logged (reviewer, timestamp, pass number, evidence pointer, decision).
   - `review_status` stays `pending` until the required passes are complete. Unvalidated records do not count as confirmed gold.

---

## (d) Frozen-core membership

**No frozen-core membership change is required** for the `verified_live`-only rule or for intent balance.

v2.2 already has 80 frozen records, all `verified_live`, all eval, 10 per scored intent, 20 per API, and team 43 Sales / 37 Support. Frozen records that are not `verified_live`: **0**.

`verified_live` eval pool per intent: coverage_limits 59, pricing_quote 35, pricing_comparison 30, docs_how_to 29, troubleshooting 17, capability_match 17, sales_qualification 16, human_handoff 10. Ten per intent is feasible and already achieved.

Bucket balance is **not** achieved (docs 0, coveragecompare 0, interpretation 1, history 3, pricecompare 5). It cannot be achieved under `verified_live` only, because the `docs` bucket has **0** verified_live records and `interpretation` has only **1** verified_live eval record. No alternative 80-id list is proposed that would claim each bucket can reach 5 while remaining `verified_live` only.

**Recommendation:** keep the current 80 frozen ids. Optional later work (not in this list as an id swap): live-verify additional `docs` and `interpretation` records if bucket balance is required in a later GT version.

Frozen gold **content** (not membership) that v2.3 will change is already listed above: `GT-LBS-RG-001` (tools) and `GT-LBS-DIR-221`, `GT-LBS-DM-218`, `GT-LBS-DM-224` (OSRM label).

Current frozen ids (unchanged):

GT-LBS-AC-031, GT-LBS-AC-032, GT-LBS-AC-033, GT-LBS-AC-038, GT-LBS-AC-044, GT-LBS-AC-045, GT-LBS-AC-051, GT-LBS-AC-068, GT-LBS-AC-073, GT-LBS-AC-081, GT-LBS-AC-086, GT-LBS-AC-089, GT-LBS-AC-204, GT-LBS-AC-214, GT-LBS-AC-215, GT-LBS-AC-222, GT-LBS-AC-229, GT-LBS-AC-230, GT-LBS-AC-231, GT-LBS-AC-234, GT-LBS-DIR-011, GT-LBS-DIR-012, GT-LBS-DIR-020, GT-LBS-DIR-021, GT-LBS-DIR-039, GT-LBS-DIR-043, GT-LBS-DIR-056, GT-LBS-DIR-062, GT-LBS-DIR-076, GT-LBS-DIR-080, GT-LBS-DIR-084, GT-LBS-DIR-085, GT-LBS-DIR-100, GT-LBS-DIR-108, GT-LBS-DIR-113, GT-LBS-DIR-209, GT-LBS-DIR-210, GT-LBS-DIR-216, GT-LBS-DIR-221, GT-LBS-DIR-222, GT-LBS-DM-025, GT-LBS-DM-026, GT-LBS-DM-027, GT-LBS-DM-052, GT-LBS-DM-059, GT-LBS-DM-077, GT-LBS-DM-085, GT-LBS-DM-087, GT-LBS-DM-094, GT-LBS-DM-097, GT-LBS-DM-117, GT-LBS-DM-118, GT-LBS-DM-213, GT-LBS-DM-214, GT-LBS-DM-218, GT-LBS-DM-221, GT-LBS-DM-222, GT-LBS-DM-224, GT-LBS-DM-226, GT-LBS-DM-227, GT-LBS-RG-001, GT-LBS-RG-005, GT-LBS-RG-006, GT-LBS-RG-007, GT-LBS-RG-015, GT-LBS-RG-016, GT-LBS-RG-021, GT-LBS-RG-034, GT-LBS-RG-038, GT-LBS-RG-082, GT-LBS-RG-084, GT-LBS-RG-104, GT-LBS-RG-212, GT-LBS-RG-213, GT-LBS-RG-225, GT-LBS-RG-226, GT-LBS-RG-231, GT-LBS-RG-232, GT-LBS-RG-233, GT-LBS-RG-234.
