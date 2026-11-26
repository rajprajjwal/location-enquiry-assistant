# Activity 16 ownership validation

The locked router matched 58 of 80 frozen owners. The target remains open, with 14 more correct assignments needed to reach 72 matches.

| Sample | Previous owner accuracy | Revised owner accuracy |
|---|---:|---:|
| Development (82) | 69/82 (84.15%) | 81/82 (98.78%) |
| Fresh working-eval (45) | 28/45 (62.22%) | 34/45 (75.56%) |
| Frozen (80) | 57/80 (71.25%) | 58/80 (72.50%) |

The rules corrected all 12 reviewed development misses across workload estimates and comparisons, regional and product fit, and history-dependent pricing. The fresh sample used whole groups excluded from development. Eight fresh owners were corrected and two regressed. The paired frozen run reused the saved live interpretation for each case and excluded the holdout. Four frozen owners were corrected and three regressed.

Escalation decisions, handoff reasons, and pending approval behavior matched the prior router on all three samples. On frozen, recall, precision, and reason coverage were each 100% across the 10 expected handoffs. The fresh sample had one false escalation in both versions and zero gold escalation positives.

On frozen, 20 of the 22 owner misses were disagreements between Sales and Support L1. The other two were disagreements over which team should handle an actual handoff. A billing-policy handoff went to Support L2 instead of Sales. A reported address-quality issue went to Maps engineering instead of Support L2. These distinctions were recorded for policy review.

The fresh sample exposed a classification question about routine cost estimates. The existing working labels assigned a single-provider Directions cost estimate to Sales (DIR-025) and a single-provider Route Matrix cost estimate to Support L1 (DM-120). An explicit rule is needed for what makes a workload estimate a Sales decision. The gold labels were preserved.

The automated suite passed 277 tests. The corpus freshness test was skipped because this checkout had no local raw snapshot.
