# Frozen routing verification

We scored the updated production router on the same 80 approved frozen cases, reusing the saved live interpretations. Ambiguous handoffs were classified through the institute endpoint.

| Metric | Result |
|---|---:|
| Owner accuracy | 59/80 (73.75%) |
| Escalation precision | 100.00% |
| Escalation recall | 100.00% |
| Provisional owners | 62 |
| Deferred status | 2 |

Deferred cases: GT-LBS-DIR-020, GT-LBS-DIR-021.

| Case | Owner | Status | Provisional | Deferred | Reason |
|---|---|---|---|---|---|
| GT-LBS-AC-031 | Account team (Sales) | unknown | True | False | Customer status is unknown. Provisional owner: Account team (Sales). The customer needs a price comparison between providers. |
| GT-LBS-AC-032 | Account team (Sales) | unknown | True | False | Customer status is unknown. Provisional owner: Account team (Sales). The customer needs a price comparison between providers. |
| GT-LBS-AC-033 | Account team (Sales) | unknown | True | False | Customer status is unknown. Provisional owner: Account team (Sales). The customer needs a price comparison between providers. |
| GT-LBS-AC-045 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-AC-051 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-AC-068 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. A routine price estimate or billing question can use the provider's published rates. |
| GT-LBS-AC-073 | Support L1 | existing | False | False | An existing customer needs service guidance. |
| GT-LBS-AC-081 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. no escalation (support) |
| GT-LBS-AC-086 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. no escalation (support) |
| GT-LBS-AC-089 | Account team (Sales) | unknown | False | False | Escalation rule matched contract request. |
| GT-LBS-AC-205 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. no escalation (support) |
| GT-LBS-AC-210 | Account team (Sales) | unknown | True | False | Customer status is unknown. Provisional owner: Account team (Sales). The customer is comparing providers against a specific product or deployment requirement. |
| GT-LBS-AC-215 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for a documented product limit or behavior. |
| GT-LBS-AC-222 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for a documented product limit or behavior. |
| GT-LBS-AC-229 | Account team (Sales) | new | False | False | A new customer needs sales qualification. |
| GT-LBS-AC-230 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. no escalation (support) |
| GT-LBS-AC-231 | Account team (Sales) | unknown | True | False | Customer status is unknown. Provisional owner: Account team (Sales). The customer needs qualification of a proposed deployment before selecting a provider. |
| GT-LBS-AC-234 | Account team (Sales) | unknown | False | False | The customer is requesting a human billing reviewer to confirm actions regarding prepaid credits for Autocomplete due to official pricing changes in September 2026. |
| GT-LBS-AC-235 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. no escalation (support) |
| GT-LBS-AC-236 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. A routine price estimate or billing question can use the provider's published rates. |
| GT-LBS-DIR-011 | Account team (Sales) | unknown | True | False | Customer status is unknown. Provisional owner: Account team (Sales). The customer is assessing a deployment or asking for a commercial comparison. |
| GT-LBS-DIR-012 | Account team (Sales) | unknown | True | False | Customer status is unknown. Provisional owner: Account team (Sales). The customer is assessing a deployment or asking for a commercial comparison. |
| GT-LBS-DIR-020 | Support L1 | unknown | True | True | Customer status was deferred. Provisional owner: Support L1. A routine price estimate or billing question can use the provider's published rates. |
| GT-LBS-DIR-021 | Support L1 | unknown | True | True | Customer status was deferred. Provisional owner: Support L1. A routine price estimate or billing question can use the provider's published rates. |
| GT-LBS-DIR-039 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. no escalation (support) |
| GT-LBS-DIR-043 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-DIR-084 | Account team (Sales) | unknown | False | False | Escalation rule matched production incident. |
| GT-LBS-DIR-085 | Account team (Sales) | unknown | False | False | Escalation rule matched contract request. |
| GT-LBS-DIR-100 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. no escalation (support) |
| GT-LBS-DIR-108 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-DIR-113 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. no escalation (support) |
| GT-LBS-DIR-201 | Account team (Sales) | unknown | True | False | Customer status is unknown. Provisional owner: Account team (Sales). The customer is assessing a deployment or asking for a commercial comparison. |
| GT-LBS-DIR-210 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. no escalation (support) |
| GT-LBS-DIR-216 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. no escalation (support) |
| GT-LBS-DIR-221 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-DIR-222 | Support L2 | unknown | False | False | The customer is requesting a handoff to a human support owner for an issue involving the Directions API on a newly created Google Cloud project, indicating the need for technical investigation. |
| GT-LBS-DIR-223 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-DIR-224 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-DIR-225 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-DIR-226 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-DM-026 | Support L1 | existing | False | False | An existing customer needs service guidance. |
| GT-LBS-DM-027 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. A routine price estimate or billing question can use the provider's published rates. |
| GT-LBS-DM-059 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-DM-085 | Maps engineering | unknown | False | False | Escalation rule matched data quality. |
| GT-LBS-DM-087 | Support L2 | unknown | False | False | Escalation rule matched security incident. |
| GT-LBS-DM-094 | Account team (Sales) | new | False | False | A new customer needs sales qualification. |
| GT-LBS-DM-097 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-DM-117 | Account team (Sales) | unknown | True | False | Customer status is unknown. Provisional owner: Account team (Sales). The customer needs a price comparison between providers. |
| GT-LBS-DM-118 | Account team (Sales) | unknown | True | False | Customer status is unknown. Provisional owner: Account team (Sales). The customer needs a price comparison between providers. |
| GT-LBS-DM-201 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. no escalation (support) |
| GT-LBS-DM-214 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. The customer needs documented capacity for a single API call. |
| GT-LBS-DM-218 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-DM-221 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. no escalation (support) |
| GT-LBS-DM-222 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. no escalation (support) |
| GT-LBS-DM-224 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. no escalation (support) |
| GT-LBS-DM-226 | Account team (Sales) | new | False | False | A new customer needs sales qualification. |
| GT-LBS-DM-227 | Account team (Sales) | new | False | False | A new customer needs sales qualification. |
| GT-LBS-DM-231 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-DM-232 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-DM-233 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. A routine price estimate or billing question can use the provider's published rates. |
| GT-LBS-RG-001 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-RG-005 | Account team (Sales) | unknown | True | False | Customer status is unknown. Provisional owner: Account team (Sales). The customer needs provider options and a cost comparison for a deployment. |
| GT-LBS-RG-006 | Account team (Sales) | unknown | True | False | Customer status is unknown. Provisional owner: Account team (Sales). The customer needs provider options and a cost comparison for a deployment. |
| GT-LBS-RG-007 | Account team (Sales) | unknown | True | False | Customer status is unknown. Provisional owner: Account team (Sales). The customer needs provider options and a cost comparison for a deployment. |
| GT-LBS-RG-015 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. A routine price estimate or billing question can use the provider's published rates. |
| GT-LBS-RG-016 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. A routine price estimate or billing question can use the provider's published rates. |
| GT-LBS-RG-021 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. A routine price estimate or billing question can use the provider's published rates. |
| GT-LBS-RG-082 | Support L1 | existing | False | False | An existing customer needs service guidance. |
| GT-LBS-RG-084 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. no escalation (support) |
| GT-LBS-RG-201 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. no escalation (support) |
| GT-LBS-RG-212 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for a documented product limit or behavior. |
| GT-LBS-RG-213 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for a documented product limit or behavior. |
| GT-LBS-RG-225 | Account team (Sales) | new | False | False | A new customer needs sales qualification. |
| GT-LBS-RG-226 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-RG-231 | Support L2 | unknown | False | False | Exposed credentials or unauthorized usage |
| GT-LBS-RG-232 | Support L2 | unknown | False | False | The customer is reporting an address-quality issue related to Google reverse geocoding results not matching the selected building, which requires support investigation. |
| GT-LBS-RG-233 | Account team (Sales) | unknown | False | False | Explicit request for a human handoff to review policy or contract related to storing Google reverse-geocode payloads and using them on an internal map. |
| GT-LBS-RG-234 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-RG-235 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |
| GT-LBS-RG-236 | Support L1 | unknown | True | False | Customer status is unknown. Provisional owner: Support L1. This enquiry asks for technical guidance or troubleshooting. |

The workbook SHA-256 was identical before and after evaluation. All handoff proposals require pending human approval.

Compared with the prior run, owner accuracy improved from 58/80 (72.50%) to 59/80 (73.75%). RG-082 changed from provisional Sales to confirmed existing-user Support L1. No other owners changed. Provisional owners decreased from 63 to 62. DIR-020 and DIR-021 remain deferred and suppress the repeated status question. Escalation decisions were identical.
