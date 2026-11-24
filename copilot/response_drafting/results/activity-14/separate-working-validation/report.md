Separate working-eval validation — 23 November 2026

The locked diagnostic implementation was tested on one case from each of the 20 remaining unused working-eval groups. Selection used all remaining groups and a fixed hash to select a case within each group. The set has nine Autocomplete, one Distance Matrix and ten Reverse Geocode cases, with no Directions cases. No frozen or holdout cases were selected or scored.

Expected questions were reviewed and locked before predictions. All 20 labels were assistant-reviewed under user delegation. This is separate-case exploratory validation, not independent human acceptance. There are two positive questions, each requiring one fact, and 18 empty lists. These reviewed labels were saved separately without modifying the GT workbook.

Both methods used the same fixed runtime, BM25 retrieval, model endpoint and shared diagnostic state. The baseline predates pricing qualification. The updated method is the configuration that scored F1 1.000 on the preceding 32 development cases. No implementation changes were made during this validation.

| Metric | Baseline | Locked updated implementation |
| --- | ---: | ---: |
| Clarifying-question F1 | 0.000 | 0.000 |
| Approved questions matched | 0/2 | 0/2 |
| Required facts covered | 0/2 | 0/2 |
| Questions generated | 0 | 0 |
| Questions on the 18 empty-label cases | 0 | 0 |

The 18 empty-label cases were handled correctly. Both positive authentication cases missed the request question. The earlier development score therefore does not establish that the follow-up implementation generalizes.

GT-LBS-RG-034 reports REQUEST_DENIED after adding location_type=ROOFTOP. The reviewed expectation asks for the redacted failing request. The model treats a documented possible missing-key cause as sufficient to skip customer evidence. The shared extractor also misses REQUEST_DENIED, and the policy allows only none.

GT-LBS-RG-102 reports REQUEST_DENIED with a Places-enabled key. The reviewed expectation asks for the redacted failing request. The model correctly proposes request_reproduction, but the policy replaces it with none because the named status is not in shared facts and its symptom matching does not recognize this wording.

Routes, next actions, owners, approvals, proposed actions, active questions and pending replies matched in all 20 pairs. No case in this set exercised an active pending reply. The prior separate four-case reopening verification remains distinct evidence. The endpoint completed 83 calls with no recorded errors or excluded attempts.

The next working-eval change should normalize named provider response statuses into the shared fact contract, permit request evidence for unresolved authentication failures, and distinguish possible documentation causes from customer-confirmed facts. Verify known causes, supplied requests and declined questions still suppress repetition, and preserve workflow routes and pending replies. These 20 cases become development cases if used to implement those changes. Do not represent a subsequent rescore on them as fresh validation.

A frozen rerun is not recommended yet. The next acceptance check needs coverage beyond the eight positive questions in the earlier development set and the two positives here. No unused groups remain within this reserved working-eval pool, so further separate validation needs newly reserved cases or newly authored and reviewed scenarios.

The evaluated runtime and labels retain their recorded hashes. New reliability instrumentation appeared in five live modules after the snapshot and was left untouched. Those changes are outside this validation. See runtime-verification.json and run-manifest.json for the exact scope.

Saved evidence includes review-cases.json, locked-gold.json, predictions.jsonl, question-review.bound.json, scores.json, behavior.json and miss-analysis.json. Output matching was assistant-reviewed and bound to the exact predictions and label hashes. From the repository, run PYTHONPATH=. .venv/bin/python -B copilot/response_drafting/results/activity-14/separate-working-validation/rescore.py to reproduce the saved metrics.
