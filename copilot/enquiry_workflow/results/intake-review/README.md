# Intake and fact-binding verification

The first review covers enquiry validation, customer-only history, provider roles, workload
assertions, explicit estimate assumptions and later customer corrections. It does not establish
complete API/intent accuracy, answer F1 or equivalence of every live workflow route.

| Check | Result |
|---|---:|
| Existing working-eval inputs | 88 |
| Provider mentions matching the reviewed reference | 88/88 |
| Current provider matching the unambiguous reference | 80/80 |
| Ambiguous current-provider cases excluded from that score | 8 |
| Provider handoff consistent with interpretation rules | 88/88 |
| Exact fact evidence and source offsets valid | 88/88 |
| Shared diagnostic state schema valid | 88/88 |
| Arbitrary scalar selections removed from multi-provider inputs | 7 |
| Other operational extraction unchanged | 83/88 |
| Workload inputs kept separately as explicit estimate assumptions | 5 |
| Unexpected changes to other operational facts | 0 |
| Frozen cases / holdout cases / live model calls | 0 / 0 / 0 |

The provider reference is assistant-reviewed. It is not independent human acceptance. The
80 scored records are working-eval cases, not the 80 frozen acceptance records. Input IDs,
groups and folds are checked against the pinned 317-case working allowlist.

The targeted interpretation and workflow suites passed **625 tests and 4 subtests**. They
include initial and reopened provider clarification, ambiguous replies, explicit replacement,
case isolation, history corrections, route and pending-reply preservation, and combined
comparison tool execution. They do not prove route equivalence across all 88 live cases.

From the repository root, rerun the offline fact check:

```sh
.venv/bin/python -B -m copilot.enquiry_workflow.verification.verify_intake
```

Run the relevant automated suites:

```sh
.venv/bin/python -B -m pytest -q tests/enquiry_interpretation tests/enquiry_workflow -p no:cacheprovider
```

`inputs.json` contains the selected enquiries and history. `provider-reference.json` contains
the reviewed expectations and ambiguity notes. `before-extraction.json` and
`after-extraction.json` retain the before/after facts. `scores.json` records the offline checks.
`manifest.json` pins input and source hashes; source snapshots preserve the reviewed code.
`test-summary.json` records the automated-suite result.

No GT labels or frozen acceptance outputs were changed. The next review covers API/intent
classification and its handoff to workflow routing.
