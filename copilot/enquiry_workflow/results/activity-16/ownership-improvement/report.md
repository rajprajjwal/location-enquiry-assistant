# Ownership improvement verification

The target has not been achieved. Owner accuracy improved by three cases, from 61/80 (76.25%) to 64/80 (80%). Eight additional correct assignments are needed to reach 72/80.

The promoted rules recognize business requirements during provider discovery and product-fit questions. They preserve the distinction between unknown customer status and provisional Sales ownership. Explicit existing-customer status retains Support, and per-call capacity exceptions are preserved.

| Check | Baseline | Candidate |
|---|---:|---:|
| Existing 159 working cases | 143/159 (89.94%) | 151/159 (94.97%) |
| New routine working cases | 24/26 (92.31%) | 24/26 (92.31%) |
| Frozen with approved owner corrections | 61/80 (76.25%) | 64/80 (80.00%) |

The new validation sample was selected as 31 records in whole groups, excluding the 159 prior cases and their groups. Five model-handoff cases were excluded after institute endpoint failures. The remaining 26 routine cases were scored. They did not exercise a changed ownership decision, so this sample supports lack of observed regression but does not independently confirm the eight development gains.

All 74 targeted tests passed with the real interpretation validator, including status, provisional ownership, capacity exceptions, handoffs, persistence and deferred replies.

The frozen comparison replays the updated routine router using the same saved interpretations and saved handoff classifications. No new model calls were used in this comparison. Escalation precision and recall remain 100%; this is preservation of the prior decisions rather than a fresh handoff-model measurement. The two user-approved label corrections are applied. No new GT labels were changed.

Corrected owners: AC-205, DM-201 and RG-201. Provisional owners remain 62. DIR-020 and DIR-021 remain deferred and suppress repeated status questions.

A read-only check of the local case database found no exact-query matches with confirmed new/existing customer facts for the 16 remaining mismatches. Missing customer evidence is still unresolved.

## Remaining mismatches

| Case | Expected owner | Provisional owner | Deferred |
|---|---|---|---|
| GT-LBS-AC-230 | Account team (Sales) | Support L1 | False |
| GT-LBS-AC-236 | Account team (Sales) | Support L1 | False |
| GT-LBS-DIR-020 | Account team (Sales) | Support L1 | True |
| GT-LBS-DIR-021 | Account team (Sales) | Support L1 | True |
| GT-LBS-DIR-039 | Account team (Sales) | Support L1 | False |
| GT-LBS-DIR-043 | Account team (Sales) | Support L1 | False |
| GT-LBS-DIR-113 | Account team (Sales) | Support L1 | False |
| GT-LBS-DIR-216 | Account team (Sales) | Support L1 | False |
| GT-LBS-DM-027 | Account team (Sales) | Support L1 | False |
| GT-LBS-DM-117 | Support L1 | Account team (Sales) | False |
| GT-LBS-DM-118 | Support L1 | Account team (Sales) | False |
| GT-LBS-DM-221 | Account team (Sales) | Support L1 | False |
| GT-LBS-DM-222 | Account team (Sales) | Support L1 | False |
| GT-LBS-DM-233 | Account team (Sales) | Support L1 | False |
| GT-LBS-RG-226 | Account team (Sales) | Support L1 | False |
| GT-LBS-RG-234 | Account team (Sales) | Support L1 | False |
