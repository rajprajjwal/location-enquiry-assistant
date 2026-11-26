Activity 14 locked frozen evaluation — 24 November 2026

The implementation that passed the 52-case working-eval regression was locked by source hashes and evaluated on the same ordered 80 eval-freeze-v4 cases. No code, retrieval settings, question labels or thresholds were changed during the run. Both methods use BM25 retrieval and the same institute endpoint. The paired baseline includes the pricing and shared-diagnostic work but predates the REQUEST_DENIED extractor, policy and prompt change.

| Metric on the same 80 frozen cases | Paired baseline | Locked implementation |
| --- | ---: | ---: |
| Clarifying-question F1 | 0.000 | 0.000 |
| Whole gold questions matched | 0/75 | 0/75 |
| Gold facts covered | 4/99 (4.04%) | 4/99 (4.04%) |
| Questions produced | 13 | 13 |
| Questions on cases with empty gold lists | 8 | 8 |

Question F1 remains below the 0.80 acceptance threshold, so this run does not complete Activity 14. The earlier 1.000 working-eval score did not transfer to the frozen set. Rubric accuracy against prompting baselines was outside this question-and-behavior evaluation and was not rerun.

The original frozen GT contains 75 questions across 40 cases. Another 40 cases have empty question lists. Fact coverage uses a separate assistant-derived decomposition into 99 atomic facts, locked before predictions. The original question text and GT are unchanged. Whole-question and partial-fact matches were assistant-reviewed against the exact saved outputs and bound to the prediction and label hashes. This is not an independent human spot-check.

The four covered facts are target regions in AC-229, monthly volume in AC-231, required volume in DM-226, and monthly volume in RG-225. Each is only part of a larger gold question. For example, AC-231 expects monthly volume and Google Requests-versus-Session-Usage billing, but the output asks only for monthly volume. It earns one fact match and no whole-question match.

Thirty-five of the 40 cases with gold questions generated no questions. The other five produced incomplete or different questions. The current diagnostic menu does not cover the full frozen qualification requirements, including traffic needs, project or account status, commercial terms, retention and redistribution rights, and rollout details. Eight questions were also generated on cases whose frozen question lists are empty. These labels were retained for scoring without relabeling or exclusions.

The REQUEST_DENIED fix produced no change in scored questions in this frozen cohort. That status appears in RG-001's earlier history, where the customer explicitly declined further questions and described a request without a key. The locked implementation correctly preserves the existing decline route. The two unresolved REQUEST_DENIED cases that the fix addressed were working-eval cases and are not part of these 80 frozen cases.

Against the paired before-change baseline, routes, next actions, owners, approvals, proposed actions, active clarifications, pending replies and saved clarification history were preserved in all 80 cases. Four actual pending clarifications were answered and reopened in both methods: AC-229, AC-231, DM-226 and RG-225. Resumed behavior and pending state matched in all four. Those reply turns are excluded from initial-turn question metrics.

There are two historical route differences from the older saved Activity 14 run. DIR-108 and DIR-221 previously returned final drafts and now have escalated status with a refusal next action because the cited passage was judged not to answer the enquiry directly. Both changes are already present in the paired before-fix baseline, so this experiment does not attribute them to REQUEST_DENIED handling. The current route totals are 61 final, 15 escalated and four clarification-needed. Historical pending state was not available in that older artifact; pending preservation claims refer to the current paired replay.

All 80 app outputs passed schema validation. One staff diagnostic plan, DIR-108, failed its internal Plan validation in both methods and fell back to no suggested question. Its frozen gold question list is empty, so it does not explain the 75 missed gold questions. The replay completed 361 endpoint calls with no recorded transport errors or excluded attempts.

Post-run checks verified that frozen input bytes, frozen GT bytes, all original gold question text, the separate fact-label file, the local GT workbook bytes and the locked runtime code hashes were unchanged. Live production modules still matched the implementation lock. No holdout cases were selected or scored.

Frozen GT SHA-256 is 00a6727d142f0f00a2d35c2edaea32d4c2ebbcbabf58afe3adda793ca3b3ade1.

The lock, predictions, original questions, derived facts, bound semantic review, per-case missed facts, scores, behavior checks, historical route comparison, execution quality and integrity verification are saved alongside this report. From the repository root, reproduce the saved question scores with the following command.

```sh
PYTHONPATH=. .venv/bin/python -B copilot/response_drafting/results/activity-14/frozen-locked/rescore.py
```
