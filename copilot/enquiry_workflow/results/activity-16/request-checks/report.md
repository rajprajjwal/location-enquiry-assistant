# Activity 16 — Request checks and ownership evidence

Activity 16 remains open. This iteration improves working-eval ownership and meets its escalation-precision threshold on the evaluated working cases. Frozen ownership remains 64/80 (80%), eight correct assignments below the 72/80 target.

| Population / metric | Before | After |
|---|---:|---:|
| Same 251 working cases: owner accuracy | 238/251 (94.82%) | 243/251 (96.81%) |
| Same working cases: escalation precision | 75% | 90% |
| Same working cases: escalation recall | 100% | 100% |
| Same working cases: false escalations | 3 | 1 |
| New 26-case validation: owner accuracy | 26/26 | 26/26 |
| Combined 277 working cases: owner accuracy | 264/277 (95.31%) | 269/277 (97.11%) |
| Frozen owner accuracy | 64/80 (80%) | 64/80 (80%) |
| Frozen escalation precision / recall | 100% / 100% | 100% / 100% |
| Frozen escalation reason coverage | 100% | 100% |

## Changes and evidence

- Standard REQUEST_DENIED configuration issues and overlong request URLs can stay in first-line assessment when a staff wrapper asks who owns the issue. Explicit handoffs, security evidence, persistent problems and incidents remain outside this guard. Clear escalation rules still run first.
- A provider returning results for the customer's own inputs can establish actual use. Hypothetical, future and negated use remain unknown. Explicit new/existing customer facts retain precedence.
- Autocomplete country-filter configuration questions receive a provisional technical owner. The rule is API-scoped and excludes licensing, sanctions, contractual and rollout questions.
- Published free-allowance questions include standard credit prerequisites, while custom/enterprise negotiation remains outside this rule.

The four changes were ablated separately on working-eval. Combined, they corrected five owners with no owner regressions. DIR-057 and DM-061 no longer produce false handoffs. RG-061 gains actual-use recognition, AC-099 receives technical configuration ownership, and DIR-032 receives published-allowance guidance ownership. No record IDs occur in the routing rules.

The remaining false escalation is DIR-044. It asks about the possible service consequence of a negative balance in earlier history; it does not establish that routing has already stopped. The account-team owner is correct, but the formal escalation flag remains incorrect against gold. A separate history-aware distinction between billing-policy guidance and confirmed billing interruption still needs work. This iteration does not blanket-disable billing handoffs.

## Validation method and limitations

The candidate was evaluated on 26 cases from 21 previously unused ownership groups. Selection used stable hash order and up to six available whole groups per API, without selecting by expected owner. Both versions scored 26/26 and changed no decisions. This supports lack of observed regression, not independent confirmation of the five development gains. There are no gold escalations or predicted escalations in this cohort, so its escalation precision and recall are undefined, not 100%.

A negative-control test found that the guard also needed to recognize an incident affecting “all our production users.” This protection was added without using gold outcomes to choose a rule. All 277 working owner/escalation predictions were verified unchanged by the protective hardening. The original lock, pre-hardening scores and equivalence check are retained.

Fresh baseline interpretation/classification used the configured institute endpoint. Paired candidate comparisons and frozen evaluation replay saved interpretations and retain cached model classifications except eligible first-line triage. There are no new model calls in frozen replay; unchanged frozen escalation scores establish preservation, not fresh handoff-model performance. No frozen or holdout cases were used to select these changes.

DIR-020 and DIR-021 remain deferred, with no repeated customer-status question. No frozen owner changed or regressed. All 16 remaining owner mismatches still have unknown customer status. Their queries and review fields are in `frozen-remaining-review.csv`. Customer facts were not invented, and no GT labels were changed to improve scores.

## Regression checks

The final run passed **779 tests and 15 subtests**; the ownership-focused run passed **121 tests**. One freshness test was skipped for lack of a real local snapshot, and five existing RAG chunking tests were excluded because their BGE tokenizer asset is unavailable. They are not counted as passes.

An initial broader run had five failures in separate provider-evidence and qualification checks. Those checks subsequently passed without invoking the changed ownership functions, and the final broader run passed. Both logs are retained. This iteration did not edit the provider-evidence or qualification modules.

The GT workbook remains SHA-256 `13c9018a7ecec44bc240e4c1f884aaf31965b55280050250c2cb59c967253d68`. Holdout cases scored: zero. Production record writes and customer messages sent: zero.

## Replay

From the repository root in the project environment, choose a new output directory:

```bash
python -m copilot.enquiry_workflow.verification.verify_ownership \
  --inputs copilot/enquiry_workflow/results/activity-16/request-checks/frozen-inputs.jsonl \
  --baseline-module copilot/enquiry_workflow/results/activity-16/request-checks/baseline/escalation_policy.py \
  --baseline-evidence copilot/enquiry_workflow/results/activity-16/request-checks/baseline/customer_evidence.py \
  --baseline-policy copilot/enquiry_workflow/results/activity-16/request-checks/baseline/escalation_policy.yaml \
  --output /tmp/ownership-request-check-replay-new
```

Use `python3` in place of `python` for the equivalent command. Use `working-inputs.jsonl` for all 277 working cases, `development-inputs.jsonl` for the original 251, or `fresh-inputs.jsonl` for the new 26. Replay needs no API credentials. Baseline snapshots, per-case outcomes, before/after scores, ablations, source hashes and unresolved review queues are stored alongside this report. Earlier reports remain unchanged.
