# Review log — C1 task specification

> **About this file.** Purpose: record of the reviewer policy, spec review, resolved decisions and gold-record reviews.
> Use case: evidence for acceptance criterion 2 ("Shahid reviews and signs off"); sign-off is still pending.
> Example: the 244 `review_priority=high` records need a second self-review recorded in `self_review_date` / `self_review_evidence`.

**Document under review:** `spec/spec.md` (schema version 1.0.0) and the schemas, vocabulary, mapping and validator that accompany it.  
**Reviewer policy:** Shahid reviews and signs off.  
**Sign-off:** pending. The sign-off block in `spec/spec.md` is left unsigned.

## Reviewer policy (amended criterion 2)

Criterion 2 of the row 3 acceptance criteria is amended to: **“Shahid reviews and signs off.”**

The 244 records that were `needs_two_reviewers=true` in v2.2 (45 of them frozen) have `review_priority=high` in v2.3 and v2.4; the other 277 are `standard`.

- `high` records require a mandatory second-pass self-review by Shahid, with recorded evidence, in addition to the first pass. That second pass is recorded on the record through `self_review_date` and `self_review_evidence`. Both fields may be blank until the review happens. In GT v2.4 they are blank on all 521 records.
- `standard` records require a single recorded review by Shahid.
- Evidence for a `high` second pass: prices and limits checked against the cited official span; escalation decision, owner and severity checked; policy or licensing claims checked; a short note of what was checked and the outcome.
- `review_status` stays `pending` on a record until the required passes are complete. Unvalidated records do not count as confirmed gold.

No gold-record review pass has been completed in this activity. All 521 v2.4 records remain `review_status=pending`, and the self-review fields remain blank.

## Spec review

| Date (Asia/Calcutta) | Reviewer | Pass | Scope | Decision | Evidence |
|---|---|---|---|---|---|
| 2026-11-11 | Capstone Architect (draft) | n/a — author, not sign-off | C1 spec, schemas, vocabulary, mapping, validator, v2.3 change list | Draft complete; submitted for Shahid’s review and sign-off | `spec/spec.md`; `validator/validator-report.md` (80/80 frozen gold outputs validate, 0 schema errors); original vocab diff was `vocab/vocab-diff-gt-v2_2.md` |
| 2026-11-11 | Capstone Architect (repo update) | n/a — author, not sign-off | Point the C1 artefacts at GT v2.3 after the change list was applied | Mapping, vocabulary diff and validator regenerated against v2.3; change list marked APPLIED and kept as history | `validator/validator-report.md`; `vocab/vocab-diff-gt-v2_3.md`; `gt-change-list-v2_3.md` |
| 2026-11-11 | Capstone Architect (repo update) | n/a — author, not sign-off | Point the C1 artefacts at GT v2.4 and apply Shahid’s approved decisions | Mapping, vocabulary diff and validator regenerated against v2.4; decisions 1–7 recorded as resolved; sign-off still pending | `validator/validator-report.md`; `vocab/vocab-diff-gt-v2_4.md`; `spec/spec.md` section 16 |
| — | Shahid Kamal | 1 (spec) | C1 task spec and schemas | Pending | |
| — | Shahid Kamal | 2 (self-review of the spec, because the document itself defines pricing, policy and escalation rules) | Same | Pending; to be recorded through `self_review_date` and `self_review_evidence` when it happens | |

The spec-review table is unchanged in structure (no new column was added). Self-review of gold records is recorded on the GT fields, not as an extra column here.

## Open decisions (resolved)

1. **Criterion 2 wording — resolved.** Amended to “Shahid reviews and signs off.” Sign-off stays pending and unsigned.
2. **Token method — resolved.** `ceil(chars/4)` is the approved interim method; official measurement will use the endpoint `usage` field in C10/eval.
3. **Frozen-80 bucket imbalance — resolved as an accepted known limitation.** `docs` has 0 `verified_live` records; `interpretation` has 1.
4. **Bare `Support` owner label — resolved.** Removed from the vocabulary. GT v2.4 uses `Support L2` on `GT-LBS-DIR-222` and `GT-LBS-RG-232`.
5. **Self-review columns — resolved.** `self_review_date` and `self_review_evidence` are in the GT, the envelope, the mapper and the spec. Blank is allowed until the review happens.
6. **Empty tool traces on DIR-042 and DIR-064 — resolved in GT v2.4.** Each now has one `doc_search` step.
7. **DM-093 `api_probe` wording — resolved in GT v2.4.** The reference answer now says “Verify against the cited docs.”

## Gold-record reviews

No first-pass or second-pass gold-record reviews are recorded yet. They begin after Shahid signs off the spec, and they follow the priority rules above. Frozen-core records should be reviewed first.
