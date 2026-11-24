# Activity 16 — Ownership refinement

Activity 16 remains open. The combined changes improve the evaluated working cases, but frozen owner accuracy remains 64/80 (80%). Eight additional correct frozen owners are needed for the 90% target.

## Results

| Measure | Before | After |
|---|---:|---:|
| Working owner accuracy, 251 cases | 228/251 (90.84%) | 238/251 (94.82%) |
| Working escalation precision | 50% | 75% |
| Working escalation recall | 100% | 100% |
| Working false escalations | 9 | 3 |
| Frozen owner accuracy, 80 cases | 64/80 (80%) | 64/80 (80%) |
| Frozen escalation precision | 100% | 100% |
| Frozen escalation recall | 100% | 100% |
| Frozen escalation reason coverage | 100% | 100% |

Ten working owners were corrected, with no owner regressions. Six false escalations were removed. Working escalation precision remains below the 80% target when all 251 evaluated working cases are combined. The remaining false escalations are DIR-044, DIR-057 and DM-061.

## How the changes were selected

1. On the 185 previously scored ownership cases, service-use evidence, public-service suitability and published-free-allowance rules were tested separately and together. The combined candidate improved owner matches from 175 to 179 without regressions.
2. The candidate was locked and checked on 33 cases from 32 previously unused ownership groups, selected by stable hash order across the four APIs without using expected owners. Both versions scored 24/33. This supports lack of observed regression; it does not independently confirm the four development gains.
3. Those 33 cases became development evidence for a second experiment. Five false handoffs on the combined 218 working cases were corrected by a narrow first-line triage guard. Owner matches improved from 203 to 208, and escalation precision from 60% to 90%, with no new missed gold escalations.
4. The second candidate was locked and checked on another 33 cases from 32 unused ownership groups. Matches improved from 29 to 30, with no owner regressions. False escalations fell from three to two. This cohort contains no gold escalations, so escalation recall is not measurable there; precision is zero because both remaining flagged cases are false positives.
5. Negative-control verification then broadened recognition of explicit hand-off and transfer requests. This narrowed the guard rather than adding a label-driven routing rule. All 251 working owner/escalation predictions were verified identical to the pre-hardening candidate.

The five descriptive working folds are retained in the first experiment summary. They are not presented as independent cross-validation because those development cases had already informed earlier ownership work. Earlier ownership evidence had excluded five model-handoff cases after endpoint failures; this iteration retains the original 185-case baseline and does not silently count those five as passes. All 66 newly selected cases completed, with no case exclusions. The first batch resumed after an interruption; successful per-case calls and available abstention logs are retained.

## Implementation

- `copilot/safety/customer_evidence.py` distinguishes asserted use, actual request submission and reported API errors from hypothetical or negated use. Existing explicit customer-status evidence takes precedence.
- `copilot/config/escalation_policy.yaml` adds separate provisional suitability and published-allowance rules. Known new/existing customer handling remains in place.
- `copilot/enquiry_workflow/routine_triage.py` recognizes staff ownership-assessment wrappers describing routine parameter, filtering or request-limit checks. It preserves explicit human requests, intervention evidence and new-customer status.
- The router checks this guard before consulting the ambiguous-handoff model. Clear incident rules still run first. No action executes automatically.

The original policy source history remains in the modified policy files. These changes add no inference framework or provider dependency.

## Frozen replay and limits

The final router was replayed on the same 80 frozen queries using the same saved interpretations, previously approved owner corrections and cached handoff classifications. No new model requests were made for frozen cases. The triage guard was applied where eligible; otherwise cached handoff decisions were retained. The 100% frozen escalation scores therefore establish preservation, not a fresh measurement of the handoff model.

There were no frozen owner changes or regressions. All 16 remaining owner mismatches have unknown customer status. DIR-020 and DIR-021 remain deferred, with no repeated status question. Their owners, deferral flags and pending suggestion behavior are preserved. The unresolved cases are listed in `frozen-remaining-review.csv`; no consensus or GT corrections were applied.

These working gains do not establish improved frozen generalization. Continue with working-eval analysis of the remaining false handoffs and with evidence-based customer-status or provisional-routing decisions. Do not invent customer facts, alter frozen labels to reach the target, or use holdout cases for tuning.

## Verification

The final regression run passed **679 tests and 15 subtests**. One real-snapshot freshness test was skipped, and five existing RAG chunking tests were excluded because their BGE tokenizer asset is unavailable locally. They are not counted as passes. `tests.txt` and `test-results.json` record the scope and existing dependency bundles used.

The local GT workbook remains SHA-256 `13c9018a7ecec44bc240e4c1f884aaf31965b55280050250c2cb59c967253d68`. No new labels, holdout scoring, production record changes or external customer messages were introduced.

Reproducible offline replay commands and the policy are described in `docs/ownership-routing.md`. Evidence includes per-case inputs and outputs, before/after scores, both experiment selections and locks, an immutable baseline policy snapshot, review queues and source hashes. Earlier reports remain unchanged.
