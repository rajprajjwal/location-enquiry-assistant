# Qualification plan validation

The validation-repair implementation is saved in the local project. The paired replay used the same 36 qualification working-eval cases, 28 groups, 65 original gold questions and 84 atomic facts. Frozen and holdout cases were excluded. The workbook and scored labels are unchanged.

| Measure | Before validation repair | After validation repair |
| --- | ---: | ---: |
| Clarifying-question F1 | 0.8595 | 0.8852 |
| Question precision | 92.86% | 94.74% |
| Question recall | 80.00% | 83.08% |
| Approved-fact coverage | 71/84 (84.52%) | 73/84 (86.90%) |
| Matched questions | 52/65 | 54/65 |
| Questions produced | 56 | 57 |

Both methods include monthly-workload normalization. These are fresh live runs, so differences from earlier reports also reflect endpoint variability. This comparison does not isolate a causal F1 gain from schema repair. Question scores use bound, assistant-inspected canonical-fact alignment, with equal grouped facts required for a whole-question match. They are development evidence, not independent human acceptance.

The two additional matches have different meanings. DM-025 recovers a useful question about input type. RG-230 receives extra credit for repeating an address-element requirement already explicit in the enquiry; the original label rewards that repetition. The higher original-label score therefore does not, by itself, establish improved qualification quality.

## Implementation

1. Validate the entire model response against the Pydantic qualification plan.
2. If only some fact entries are invalid, omit those entries while preserving valid facts, question groups and reasons; validate the complete plan again.
3. If errors remain, allow one model repair within the existing gateway retry, token and deadline limits. Transport retries and schema repair share retry credits.
4. Admit extracted facts only after complete-plan validation and customer-evidence checks. If repair fails, preserve active questions and pending replies; the deterministic pricing path is available only when pricing eligibility is the sole allowed decision.

The audit records response hashes, validation stages and input-free field/type errors. Schema-invalid entries are not automatically considered false; omitting them leaves their customer facts unconfirmed.

## Verification

- All 11 behavior checks passed for 36/36 paired cases, including routes, next actions, owners, approvals and pending replies.
- All four cases reopened in a separate database connection preserved their reply behavior.
- Preservation establishes no regression; it does not establish correctness. Both versions still repeat the provider question in RG-227 after the customer supplies Mapbox, because `provider` and `current_provider` are inconsistently bound.
- Final integrated turn statuses: `{"locally_repaired": 3, "no_validation_audit": 4, "valid": 33}`. Initial and resumed turns are counted separately; `no_validation_audit` means this selector did not publish a qualification audit and does not establish that no model call occurred. Excluded endpoint attempts remain in the raw audit.
- 3 naturally occurring invalid plans recovered during this replay. Per-turn errors and recovery details are in `summary.json` and `full-36/validation-audit.jsonl`.
- The observed RG-228 monthly-volume response failed at `supplied_facts.0.evidence` because the evidence string was empty. A controlled replay injects this same captured response into both methods. The repaired method omits that invalid entry and validates locally, using one logical request and no schema-repair call. Core behavior and the reopened reply remain unchanged. This is a controlled fault replay, not another naturally reproduced failure.
- DM-030's historical failure did not reproduce. The old log recorded only `ValidationError`, so its original failing field cannot be established retrospectively.
- 417 automated tests and four subtests passed, including malformed/truncated JSON, exhausted retries, token/deadline limits, fact grounding and no third fallback model request.
- One AC-024 pair encountered two HTTP 429 errors and was rerun; its clean pair is scored and the excluded attempt remains recorded.

## Remaining qualification review

`working-label-review.json` contains proposals only; none were applied to scoring. Several original questions repeat details already supplied, while other cases expose genuine fact-binding issues: daily outlets do not necessarily equal stops in one route, DM-034 asks again for usage geography already placed in India, and RG-227 repeats a provider question after reopening. The storage yes/no match in AC-233 does not establish retention-duration coverage. These require separate qualification work and reviewed labels before an acceptance rerun. Schema repair is verified; overall Activity 14 acceptance remains open. No frozen rerun was performed.

## Saved evidence

- `full-36/predictions.jsonl`: paired drafts, questions and case-state snapshots.
- `full-36/scores.json`, `question-alignment.json`, `question-review.bound.json`: metrics and hash-bound alignment.
- `full-36/run-manifest.json`, `behavior.json`, `validation-audit.jsonl`, `plan-responses.jsonl`: locked sources, checks and responses.
- `captured-fault-final/`: final controlled recovery replay.
- `reproduction.json`, `captured-plans.jsonl`: original reproduction.
- `schema-only-smoke/` and `schema-only-check/`: earlier model-only development attempts, retained separately from final results.

To recompute metrics from saved outputs, run from the repository root:

```sh
PYTHONPATH=. .venv/bin/python -B copilot/response_drafting/results/activity-14/qualification-validation/full-36/rescore.py
```
