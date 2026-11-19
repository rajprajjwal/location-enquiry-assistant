# Activity 4 frozen-core audit

Verified 18 November 2026. **All Activity 4 acceptance checks passed.** Both tags contain the same 80 evaluation case IDs.

| Criterion | Target from Activities.xlsx | Verified result |
|---|---|---|
| Set size | 60–100 cases | 80 |
| Scenario balance | At least 5 in each of 10 buckets | 5–15 in each bucket |
| API balance | At least 15% per API | autocomplete 20 (25%), directions 20 (25%), distance_matrix 20 (25%), reverse_geocode 20 (25%) |
| Team balance | 40–60% per team | Sales 47 (58.75%), Support 33 (41.25%) |
| Frozen membership | Eval cases only | 80 eval, 0 holdout, 0 duplicate IDs |
| Original freeze timing | Tag commit before first interpreter or agent code | `eval-freeze-v2` is a Git ancestor of `3345ff4` |

## Bucket counts

| Bucket | Definition | Cases |
|---|---|---:|
| `capabilitycompare` | Compares whether providers or APIs support the features the customer needs. | 11 |
| `coveragecompare` | Compares where providers or APIs offer service for the requested use case. | 5 |
| `docs` | Answers a documented how-to, parameter, integration, or usage-policy question. | 5 |
| `history` | Uses earlier conversation turns to interpret the current enquiry and carry forward relevant facts. | 5 |
| `interpretation` | Tests identifying the customer's intent, API, or responsible team from the enquiry. | 5 |
| `limitscompare` | Compares limits such as quotas, request sizes, or capacity across options. | 7 |
| `ownership` | Determines who should handle the case and whether it should be escalated. | 11 |
| `pricecompare` | Compares costs using the same workload, billing assumptions, and currency basis. | 5 |
| `qualification` | Captures stated customer requirements and identifies missing information needed to qualify the request. | 15 |
| `updates` | Determines whether to propose a sandbox record update and which fields it should contain. | 11 |

## Freeze evidence

| Git tag | Purpose | Commit | Verified gold SHA-256 | Evidence |
|---|---|---|---|---|
| `eval-freeze-v2` | Original pre-implementation freeze | `22e7973` | `151f87f56ae91fbbb9c8977e09c0151efb1c14cd500877354bb3826a1f349123` | [Manifest](https://github.com/ssshahid99/location-enquiry-assistant/blob/eval-freeze-v2/eval/freeze-manifest.json) |
| `eval-freeze-v4` | Revised Activity 2 scoring baseline | `f0cef00` | `bfe30735cf4cbb985e9618b868f58a00c61bce6b7866df2fb3433d83ed23c357` | [Manifest](https://github.com/ssshahid99/location-enquiry-assistant/blob/eval-freeze-v4/eval/frozen-interpretation/manifest.json) |
