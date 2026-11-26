# Activity 16 pricing ownership verification

The approved policy is implemented. The 90% owner-accuracy requirement remains open.

| Sample | Prior router | Approved pricing policy |
|---|---:|---:|
| Development | 131/147 (89.12%) | 104/147 (70.75%) |
| Fresh working-eval | 8/12 (66.67%) | 8/12 (66.67%) |
| Frozen | 58/80 (72.50%) | 54/80 (67.50%) |

The initial 20-case fresh validation scored 8/20 against 16/20 for the prior router. Six owner differences were comparisons between billing options within one provider. Two genuine provider-selection cases exposed a gap for enquiries that asked for options without naming a vendor. The final router corrected those two cases, and a separate 12-case working sample verified the revised behavior.

The working-eval label review contains 30 proposed owner changes (22 to Support L1 and 8 to Sales). The workbook and frozen benchmark retain their original labels.

We scored the same 80 approved frozen cases using their saved live interpretations, with holdout cases excluded. All ten expected escalations had reasons; none were missed or added incorrectly. Escalation decisions and pending approvals matched in the paired runs.

The real-validator routing tests passed 21 cases. The full suite passed 287 tests and skipped one corpus freshness test because the raw snapshot was unavailable.
