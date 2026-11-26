# eval/

This folder records the Activity 4 frozen core (80 records from GT v2.5) in Git. `freeze-manifest.json` contains the GT version, SHA-256 hashes of `gt_v2_5.csv`, `gt_v2_5.xlsx` and `mapping/gold_outputs_frozen.jsonl`, sorted frozen IDs, and bucket/API/team counts with the Activity 4 thresholds and results.
To reproduce this historical freeze, check that `sha256sum mapping/gold_outputs_frozen.jsonl` matches the manifest and that `eval-freeze-v2` points to the commit holding it. The earlier `eval-freeze-v1` is retained in the manifest's `history` field. Raw GT was kept outside Git for that freeze and bound by hash. The current workbook is `data/ground-truth.xlsx`; use the current evaluation guide for later runs.
