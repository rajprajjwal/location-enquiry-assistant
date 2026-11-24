# Ownership and escalation: final end-to-end audit

The stated Activity 16 acceptance targets are met on the same 80 frozen cases. Owner accuracy improves from 64/80 to 72/80. The ground-truth workbook is unchanged, no holdout cases were used, and no production action was executed.

## Acceptance result

| Measure | Required | Final result |
| --- | --- | --- |
| Owner/role accuracy | ≥90% | **72/80 (90%)**, previously 64/80 (80%) |
| Escalation recall | ≥90% | **10/10 (100%)** |
| Escalation precision | ≥80% | **10/10 (100%)** |
| Escalation reason present | 100% | **10/10 (100%)** |

Eight owner decisions improved, with no new frozen owner regressions. DIR-020 and DIR-021 retain their deferred status, original provisional route and no repeated status question.

## Root causes and fixes

- **Customer evidence was disconnected from the UI.** The case runner could read confirmed status, but the UI did not collect it. It now accepts an optional confirmed relationship and stores source-linked evidence. Reopening reuses it; deleting the source removes it instead of propagating stale confirmation through later snapshots. Different cases remain isolated.
- **Clarification history was incomplete.** Saved clarification messages were omitted from routing history. They now appear as assistant turns, allowing short answers such as “new” to resolve the preceding status question. Unsent drafts remain excluded.
- **Generic technical defaults absorbed commercial decisions.** Explicit deployment quotes and licensing/reuse decisions now receive provisional Sales ownership when status is unknown. Confirmed relationships and handoff decisions retain priority.
- **Feature-discovery ownership was ambiguous.** The confirmed policy assigns Sales to all provider-feature discovery when customer status is unknown, including inventory questions without an explicit buying request. Specific numeric per-request feasibility remains technical documentation. Customer status itself stays unknown.
- **API contention stopped validation.** The endpoint returned `per-key concurrent request limit exceeded`. The shared client now serializes newly started local processes using the same key, within the enquiry deadline. The competing workflow runner was paused with approval and has been resumed.
- **Historical replay was mistaken for fresh evidence.** A new verifier generates fresh interpretations and handoff classifications, keeps failed cases visible, and never passes scoring labels to the model. A legitimate semantic abstention keeps the production provisional-owner route rather than being dropped from evaluation.

## Validation method

Fresh interpretation and routing were measured on 17 working cases selected as complete groups by stable hash: 16/17 owners were correct, with four gold escalations detected and no false escalations. That gate passed before the 80-case fresh frozen run.

The final role-policy changes were validated on working-eval and locked before deterministic routing replay over those freshly generated model interpretations. Fresh handoff classifications were retained because the new ownership rules do not enter the handoff path. Final scores therefore measure **locked routing replay on fresh model outputs**, not an additional stochastic 8B run after the last policy clarification. Full inputs, first-pass outputs, source hashes and the semantic-abstention scoring correction are retained.

The frozen set has been inspected repeatedly during development. This is an acceptance check on that set, not an unseen generalization estimate. Holdout data remains untouched.

## Working-eval tradeoff

| Cohort | Previous owner accuracy | Final owner accuracy | Escalation precision / recall |
| --- | --- | --- | --- |
| 286 saved working cases | 276/286 (96.50%) | **269/286 (94.06%)** | 90% / 100% |
| 17 freshly interpreted working cases | 16/17 (94.12%) | **16/17 (94.12%)** | 100% / 100% |

Seven working feature-discovery records still carry Support gold labels while the confirmed policy assigns Sales. These remain scored as mismatches; no label was changed or silently excluded. They are listed in `working-label-policy-disagreements.csv`. This tradeoff must be kept visible when comparing results across policy versions.

A broad model-based ownership override was rejected: it reduced working accuracy to 263/286 (91.96%) from 276/286. A short supporting quote alone did not make the model's task classification reliable. The app uses the narrow, confirmed policy decisions instead.

## Verification and remaining errors

- **998 automated tests passed**, one freshness test skipped because no real snapshot was available; 15 subtests passed. Five existing tokenizer-dependent chunking tests were excluded.
- The Streamlit integration test verifies relationship selection → routing → saved case → reopening. Backend tests also verify corrections, isolation, source deletion, deferrals and pending approvals.
- Cross-process gateway tests verify key exclusion, independent keys and lock release after failure.
- Eight frozen owners still differ from gold. Their queries and history are in `owner-context-review.csv`; the form does not assume those labels are incorrect. Remaining errors and the seven working label-policy disagreements are follow-up work, not hidden score adjustments.
- No model weights, frozen labels, holdout records, production records or external messages were changed.

## Reproduce fresh interpretation and routing

Activate the project environment and configure `TRACKB_API_KEY` and `TRACKB_CA_CERT` using the model-client setup guide. Leave `TRACKB_GT_CSV` unset. From the repository root, choose a new output directory:

```bash
python -m copilot.enquiry_workflow.verification.verify_ownership_live \
  --inputs copilot/enquiry_workflow/results/activity-16/end-to-end-audit/frozen-inputs.jsonl \
  --output /tmp/ownership-live-new
```

```bash
python3 -m copilot.enquiry_workflow.verification.verify_ownership_live \
  --inputs copilot/enquiry_workflow/results/activity-16/end-to-end-audit/frozen-inputs.jsonl \
  --output /tmp/ownership-live-new-python3
```

`final-summary.json` is the final scorecard. `final-frozen/` contains the final 80 predictions and scores; `live-frozen/` contains fresh model evidence; `final-working/` and `final-fresh-working/` contain the working validations. `approved-policy.json`, `final-runtime-lock.json`, `source-snapshot/`, and the test logs retain the policy and implementation evidence. Earlier experiment results remain for auditability and are not active app logic.
