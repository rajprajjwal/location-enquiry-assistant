Named-error diagnostic regression — 24 November 2026

REQUEST_DENIED is now captured as a shared error-code fact with its source and evidence, including lowercase input. The diagnostic policy recognizes an observed unresolved denial and selects a redacted failing-request question. A possible documentation explanation no longer establishes that the customer has that configuration. Definition questions, explicit known causes, supplied requests and asked or declined request questions retain their suppression behavior.

Implementation is contained in copilot/diagnostics/extraction.py, policy.py and planning.py. No routing or pending-reply implementation was changed. The change affects staff question suggestions while preserving active clarification behavior. Focused verification is in tests/enquiry_workflow/test_request_denied.py.

All 52 working-eval cases were replayed before and after the change using the same current workflow snapshot, BM25 retrieval and institute endpoint. Both methods include pricing qualification and current reliability instrumentation. Only error extraction, diagnostic policy and its prompt differ. Existing reviewed questions and atomic facts were kept unchanged.

| Metric across 52 cases | Before | After |
| --- | ---: | ---: |
| Clarifying-question F1 | 0.889 | 1.000 |
| Whole questions matched | 8/10 | 10/10 |
| Required facts covered | 14/16 (87.50%) | 16/16 (100%) |
| Question precision | 100% | 100% |
| Question recall | 80% | 100% |
| Questions on 42 empty-label cases | 0 | 0 |

| Cohort | F1 before | F1 after | Fact coverage before | Fact coverage after |
| --- | ---: | ---: | ---: | ---: |
| Previous 32 cases | 1.000 | 1.000 | 14/14 | 14/14 |
| Additional 20 cases | 0.000 | 1.000 | 0/2 | 2/2 |

Both previously missed cases, GT-LBS-RG-034 and GT-LBS-RG-102, now produce the expected redacted-request question.

> Could you share an example of the failing request as sent, with tokens and credentials redacted?

Routes, next actions, owners, approvals, proposed actions, active clarification questions, pending replies and saved clarification history matched in all 52 paired replays. None of the 52 had an active pending reply, so four additional working-eval conversations were reopened separately. Pending state and resumed behavior matched in all four. Those four cases are excluded from question metrics.

The 52-case replay completed 266 model calls with no recorded endpoint errors or excluded attempts. All app outputs passed their schema checks. Targeted automated verification passed 314 tests and four subtests. Tests cover named-error provenance, lowercase input, unresolved denial, possible documentation causes, definition questions, explicit known causes, supplied requests, asked or declined requests, assistant-history exclusion and unchanged workflow fields.

These are development/regression results. Labels for 18 cases were user-approved and 34 were assistant-reviewed under explicit delegation. Whole-question matches and atomic fact matches were assistant-adjudicated against the unchanged labels. Reviews are bound to the exact prediction and label hashes. There are ten positive questions, so a perfect score on this set does not establish independent acceptance or generalization to all enquiry types.

No frozen or holdout cases were selected or scored, and no GT workbook labels were edited. The locked runtime hashes were verified and all corresponding live production modules still matched at verification time.

Saved evidence includes predictions.jsonl, locked-gold.json, question-review.bound.json, scores.json, behavior.json, pending-reply-results.json, run-manifest.json, runtime-verification.json, implementation.diff and tests.txt. The reviewed case packets and label-source hashes are retained. From the repository root, run the following to reproduce the saved scores.

```sh
PYTHONPATH=. .venv/bin/python -B copilot/response_drafting/results/activity-14/request-denied/rescore.py
```
