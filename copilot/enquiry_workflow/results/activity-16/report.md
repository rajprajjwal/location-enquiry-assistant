# Activity 16 ownership and escalation verification

Scoring targets are still open.

| Metric | Target | Working baseline (49) | Working candidate (49) | Frozen candidate (80) |
|---|---:|---:|---:|---:|
| Owner accuracy | ≥90% | 79.59% | 97.96% | 71.25% |
| Escalation recall | ≥90% | 100.00% | 100.00% | 100.00% |
| Escalation precision | ≥80% | 90.00% | 100.00% | 100.00% |
| Escalations with a reason | 100% | 100.00% | 100.00% | 100.00% |

The frozen run matched 57 of 80 owners and identified 10 true escalations, with 0 false positives and 0 false negatives.

The paired working-eval check used the same saved interpretation for both routing configurations. It retained whole groups and included all nine working-eval escalation positives.

The frozen check used the approved eval-freeze-v4 inputs, the institute model for interpretation, and the production routing function. It excluded holdout cases and scored routing independently of retrieval and drafting. An escalation is a formal handoff proposal. Manual review after a drafting or retrieval failure is tracked separately.

The YAML policy assigns teams and urgency for clear signals. The model classifies ambiguous handoffs against the same allowed categories. The workflow puts consequential handoffs in the sandbox review queue as pending and unexecuted.

The local test suite passed 272 tests, with one skipped. The workflow tests also passed with the real interpretation validator enabled (63 tests).

On the frozen set, 21 of the 23 owner misses were disagreements between Sales and Support L1.
The other two were incorrect owners on otherwise correctly identified escalations.
Meeting the ownership target requires 72 exact matches, 15 more than this run achieved.

On 33 separate working-eval cases selected to test mixed Sales and Support ownership, the
locked router matched 21 owners (63.64%). An exploratory model owner classifier matched
22 (66.67%). It corrected three classifications and introduced two errors. This classifier
was evaluated independently of the frozen set and is excluded from the app.

A live synthetic Directions enquiry produced a schema-valid Support L2 handoff with a
reason and a pending approval. The app did not execute the handoff.
