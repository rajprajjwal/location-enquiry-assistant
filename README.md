# Location Services Sales and Support Copilot — Track-B C1 artefacts

> **About this file.** Purpose: entry point for the repo; explains what it holds and where the read-only sources live.
> Use case: read first before touching the spec, schemas, mapping or validator.
> Example: the GT source of truth is `/workspace/capstone-trackb/data/gt_v2_5.xlsx`, kept outside the repo and bound by SHA-256 in `eval/freeze-manifest.json`.

Local git repository for the C1 task specification of Shahid’s Track-B capstone. An origin remote may already be configured; this activity does not add remotes and does not push.

This repository holds design artefacts only: the task spec, versioned JSON Schemas, the controlled vocabulary, a mechanical GT-to-schema mapping, and a validator. It is not the application.

## Why the repo lives in this subfolder

The repository root is `/workspace/capstone-trackb/repo/`, not `/workspace/capstone-trackb/`. The parent tree contains `inputs/` (activities, the Track-B PDF, the Learner Guide, a CA certificate) and `data/` (GT workbooks, including `gt_v2_5.xlsx` and the earlier unchanged `gt_v2_4.xlsx`, `gt_v2_3.xlsx` and `gt_v2_2.xlsx`). Those files are the read-only sources for this work and must not be versioned here. Secrets, keys and certificates are also kept out. The GT file is never copied into this repository.

## Source of truth (outside the repo, read only)

- GT: `/workspace/capstone-trackb/data/gt_v2_5.xlsx` (532 records; CSV companion: `/workspace/capstone-trackb/data/gt_v2_5.csv`)
- Activities, brief, Track-B PDF, Learner Guide: `/workspace/capstone-trackb/inputs/`

## Contents

- `spec/spec.md` — task specification (sign-off unsigned / pending)
- `schemas/` — versioned JSON Schemas for the seven outputs and the envelope (`x-spec-version` 1.0.0)
- `vocab/controlled-vocabulary.json` — controlled vocabulary bound to GT v2.5
- `vocab/vocab-diff-gt-v2_5.md` and `vocab/vocab-diff-gt-v2_5.json` — current vocabulary diff against GT v2.5
- `vocab/vocab-diff-gt-v2_4.*` and `vocab/vocab-diff-gt-v2_3.*` — kept as history (the v2.4 and v2.3 diffs)
- `mapping/` — mapper, mapping notes, and generated gold envelopes (all 532 and the 80 frozen records)
- `eval/freeze-manifest.json` — Activity 4 freeze manifest (GT v2.5 hashes, frozen IDs, counts vs thresholds); tagged `eval-freeze-v1`
- `validator/validate_spec.py` — schema, vocabulary, approval, required-field and token-budget checks
- `validator/validator-report.md` — last validator run
- `gt-change-list-v2_3.md` — the v2.3 change list, marked APPLIED and kept as history
- `review-log.md` — reviewer policy and pending sign-off

## Run the validator

```bash
cd /workspace/capstone-trackb/repo
.venv/bin/python validator/validate_spec.py
```

The default run reads GT v2.5 and writes the report, gold outputs and vocabulary diff inside this repository, which is the layout that gets committed. To run without writing inside the repo:

```bash
.venv/bin/python validator/validate_spec.py --out-dir /tmp/c1-validate-out
```

The virtualenv is not committed. Recreate it with:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`requirements.txt` lists `jsonschema`, `pandas` and `openpyxl`. The validator reads the GT workbook from the path above and never writes to it.

Do not call the inference endpoint from this repository. Do not read or echo `TRACKB_API_KEY`.
