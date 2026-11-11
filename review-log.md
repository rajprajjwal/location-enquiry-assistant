# Review log — C1 task specification

**Document under review:** `spec/spec.md` (schema version 1.0.0) and the schemas, vocabulary, mapping and validator that accompany it.  
**Reviewer policy:** Shahid signs off and reviews alone (final decision for this activity).  
**Sign-off:** pending. The sign-off block in `spec/spec.md` is left unsigned.

## Policy that resolves `needs_two_reviewers`

This log does not ignore the 244 v2.2 records that were flagged `needs_two_reviewers=true` (45 of them frozen). GT v2.3 has applied the replacement:

- `needs_two_reviewers` is retired.
- `review_priority` is `high` on those 244 records and `standard` on the other 277.
- `high` records require a mandatory second-pass self-review by Shahid, with recorded evidence, in addition to the first pass.
- `standard` records require a single recorded review by Shahid.
- Evidence and both pass records are logged here (reviewer, timestamp in Asia/Calcutta, pass number, evidence pointer, decision).
- `review_status` stays `pending` on a record until the required passes are complete. Unvalidated records do not count as confirmed gold.

No gold-record review pass has been completed in this activity. All 521 v2.3 records remain `review_status=pending`.

## Spec review

| Date (Asia/Calcutta) | Reviewer | Pass | Scope | Decision | Evidence |
|---|---|---|---|---|---|
| 2026-11-11 | Capstone Architect (draft) | n/a — author, not sign-off | C1 spec, schemas, vocabulary, mapping, validator, v2.3 change list | Draft complete; submitted for Shahid’s review and sign-off | `spec/spec.md`; `validator/validator-report.md` (80/80 frozen gold outputs validate, 0 schema errors); original vocab diff was `vocab/vocab-diff-gt-v2_2.md` |
| 2026-11-11 | Capstone Architect (repo update) | n/a — author, not sign-off | Point the C1 artefacts at GT v2.3 after the change list was applied | Mapping, vocabulary diff and validator regenerated against v2.3; change list marked APPLIED and kept as history | `validator/validator-report.md`; `vocab/vocab-diff-gt-v2_3.md`; `gt-change-list-v2_3.md` |
| — | Shahid Kamal | 1 (spec) | C1 task spec and schemas | Pending | |
| — | Shahid Kamal | 2 (self-review of the spec, because the document itself defines pricing, policy and escalation rules) | Same | Pending | |

## Acceptance-criterion conflict (not marked passed)

Activities row 3 acceptance criteria include the sentence: “The spec is committed in git and all 6 team members have reviewed it.”

Shahid’s final decision is that he signs off and reviews alone. This log does not treat the six-member review as satisfied. The spec is committed in the local git repository. This activity does not push. The six-member review remains an open conflict for Shahid to resolve (amend the criterion, or commission additional reviewers).

The other row 3 measures — versioned JSON Schemas for all seven outputs, and a validator that runs over all frozen gold expected outputs with 100% passing and 0 schema errors — are reported in `validator/validator-report.md`.

## Gold-record reviews

No first-pass or second-pass gold-record reviews are recorded yet. They begin after Shahid signs off the spec, and they follow the priority rules above. Frozen-core records should be reviewed first.
