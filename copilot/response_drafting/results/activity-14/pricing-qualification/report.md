Pricing qualification working-eval regression — 23 November 2026

The comparison workflow passes missing regional pricing requirements to the shared diagnostic planner. Staff follow-ups ask for billing account country and primary usage geography when they affect the price schedule. Supplied facts, explicit global or India pricing assumptions, and declined follow-ups suppress unnecessary questions. Tariffs and pricing arithmetic are unchanged.

The baseline is the shared diagnostic implementation immediately before this pricing change. It already includes the earlier OVER_QUERY_LIMIT wording correction. Both methods use the same enquiries, BM25 retrieval, model endpoint and shared-state integration.

| Working-eval cohort | Cases | Approved questions / facts | F1 before | F1 after | Fact coverage before | Fact coverage after |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original reviewed set | 16 | 7 / 12 | 1.000 | 1.000 | 100% | 100% |
| Additional reviewed set | 16 | 1 / 2 | 0.000 | 1.000 | 0% | 100% |
| Combined | 32 | 8 / 14 | 0.933 | 1.000 | 85.71% | 100% |

Combined precision and question recall are both 100%. The updated method matches all eight approved grouped questions and all 14 atomic facts. It adds zero questions on the 24 cases whose approved lists are empty. Questions are scored against the existing labels, with semantic judgements bound to the exact prediction and label file hashes.

The previously missed pricing enquiry now receives this staff suggestion.

> Which country is your billing account based in, and where will most of these requests be used?

Routes, next actions, owners, approvals, proposed actions, active clarifications, pending replies and saved clarification history were preserved in all 32 pairs. None of these 32 cases exercised an active pending reply, so four additional working-eval conversations were reopened separately. Pending state and resumed behavior matched in all four, with no endpoint errors. Their outputs are in pending-reply-results.json.

Automated verification passed 300 tests and four subtests, including the pricing-to-workflow contract, partial geography inputs, explicit pricing assumptions, declined questions, persisted output validity and active-question preservation.

Both sets are now development/regression evidence. Labels for 18 cases were user-approved and 14 were assistant-reviewed under explicit delegation. Output matching was assistant-reviewed. This small set has eight positive questions, so its perfect score is not proof of broader generalization or independent acceptance. No frozen or holdout cases were used or rerun. Frozen GT and the reviewed labels were unchanged.

Artifacts include predictions.jsonl, locked-gold.json, question-review.bound.json, scores.json, behavior.json, pending-reply-results.json and run-manifest.json. The manifest identifies the fixed runtime and source hashes. rescore.py reproduces the saved scores using the shared bound-review scorer. Run it from the repository with PYTHONPATH=. and the project virtual environment.
