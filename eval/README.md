# eval/

Purpose: binds the Activity 4 frozen core eval set (80 records from GT v2.5) to git. `freeze-manifest.json` records the GT version, the SHA-256 of `gt_v2_5.csv`, `gt_v2_5.xlsx` and `mapping/gold_outputs_frozen.jsonl`, the sorted frozen IDs, and bucket/API/team counts with the Activity 4 thresholds and pass/fail.
Use: before any eval run, check that `sha256sum mapping/gold_outputs_frozen.jsonl` matches the manifest and that the annotated tag `eval-freeze-v2` points to the commit that holds it (`eval-freeze-v1` is superseded and kept as history; see the manifest's `history` field). Raw GT stays outside git and is bound by hash only.
