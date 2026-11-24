# Ownership status and billing follow-up validation

Activity 16 remains open. The frozen replay has 64/80 correct owners (80%); the target is 72/80. No ground-truth labels were changed, and holdout cases were excluded.

## Changes

- Recognize explicit existing-customer statements with provider modifiers, such as “Existing Google project” and “We're on Ola Maps”. Conditional statements do not establish customer status.
- Keep a continued credit-balance policy question with Sales when no interruption or request for intervention is established. Confirmed failures and human requests retain their assessment and approval paths.
- Retain provisional ownership when customer status is unknown. Preserve the two deferred frozen cases without repeating the status question.
- Reject using model team confidence alone to override the owner: on the 277 development cases it fixed two owners but regressed 19.

## Results

| Cohort | Owner accuracy | Escalation precision | Escalation recall | Escalation reason present |
| --- | --- | --- | --- | --- |
| Previous 277 working cases, baseline | 269/277 (97.11%) | 90% (9/10) | 100% (9/9) | 100% |
| Same 277, candidate | 269/277 (97.11%) | 100% (9/9) | 100% (9/9) | 100% |
| Nine unused working groups, both versions | 7/9 (77.78%) | 0% (0/1) | Not measurable: no gold escalations | 100% |
| Combined 286 working cases, candidate | 276/286 (96.50%) | 90% (9/10) | 100% (9/9) | 100% |
| Same 80 frozen cases, baseline and candidate | 64/80 (80%) | 100% (10/10) | 100% (10/10) | 100% |

The explicit-status change corrects four status classifications in the original working cohort without changing their owners. The billing continuation removes one false escalation there. Neither change triggers a routing change on the nine unused cases or the frozen cases. Fresh cases expose two existing owner mismatches and one false escalation; no new rules were selected from these results.

## Method and limitations

Candidate logic was locked before selecting and scoring nine unused whole working groups (up to three per API; no eligible Distance Matrix groups remained). Selection used group hashes, not owner labels. Live interpretation and routing completed for all nine after resuming transient HTTP 429 failures. No cases were removed because of endpoint errors. There are no positive gold escalations in this small independent cohort, so it cannot validate escalation recall or the positive billing guard independently.

The 277-case and frozen results replay saved interpretations. Cached model handoff classifications are preserved except for eligible deterministic first-line or billing-policy guards. Their escalation scores measure replay behavior and preservation, not a fresh end-to-end model benchmark. Frozen replay began only after working validation, with the implementation locked.

## Verification

- 132 focused ownership tests passed, including status assertions, intervention negative controls, routing and pending approval behavior.
- Broad offline run: 849 passed, six failed, one skipped; 15 subtests passed. The same six qualification/follow-up failures reproduce with the previous ownership policy and billing guard disabled. They remain unresolved outside this ownership change.
- Five tokenizer-dependent chunking tests were excluded; the freshness test skipped because no local snapshot was available.
- Ground-truth workbook checksum remains `13c9018a7ecec44bc240e4c1f884aaf31965b55280050250c2cb59c967253d68`.
- Deferred cases DIR-020 and DIR-021 remain deferred, with no repeated customer-status question.

## Remaining work

Reach eight additional correct frozen owners without inventing customer status or tuning rules to frozen failures. Review the working-only owner packet: two original cases conflict with the approved existing-customer support policy, and six lack explicit customer-status evidence. Audit the new independent mismatches and false escalation as a subsequent working-eval iteration. Resolve the six qualification test failures before claiming the complete suite is green.

## Saved evidence

`summary.json` contains cohort metrics; `working/` and `frozen/` retain baseline and candidate records. `fresh-inputs.jsonl` contains all nine completed live cases and model-call metadata. `fresh-selection.json`, `candidate-lock.json` and `final-lock.json` record selection and implementation hashes. `working-owner-review.csv` contains the original eight unresolved working owners. `rejected-model-team-override.json` records the rejected confidence-only approach. Test logs and `baseline/` preserve verification evidence.
