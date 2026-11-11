# Location Services Sales and Support Copilot — Track-B C1 artefacts

Local git repository for the C1 task specification of Shahid’s Track-B capstone. There is no remote and nothing has been pushed.

This repository holds design artefacts only: the task spec, versioned JSON Schemas, the controlled vocabulary, a mechanical GT-to-schema mapping, and a validator. It is not the application.

## Why the repo lives in this subfolder

The repository root is `/workspace/capstone-trackb/repo/`, not `/workspace/capstone-trackb/`. The parent tree contains `inputs/` (activities, the Track-B PDF, the Learner Guide, a CA certificate) and `data/` (GT workbooks, including `gt_v2_2.xlsx`). Those files are the read-only sources for this work and must not be versioned here. Secrets, keys and certificates are also kept out. The GT file is never copied into this repository.

## Source of truth (outside the repo, read only)

- GT: `/workspace/capstone-trackb/data/gt_v2_2.xlsx`
- Activities, brief, Track-B PDF, Learner Guide: `/workspace/capstone-trackb/inputs/`

## Contents

- `spec/spec.md` — task specification (sign-off unsigned)
- `schemas/` — versioned JSON Schemas for the seven outputs and the envelope (`x-spec-version` 1.0.0)
- `vocab/` — controlled vocabulary and a diff against GT v2.2
- `mapping/` — mapper, mapping notes, and generated gold envelopes (all 521 and the 80 frozen records)
- `validator/validate_spec.py` — schema, vocabulary, approval, required-field and token-budget checks
- `validator/validator-report.md` — last validator run
- `gt-change-list-v2_3.md` — proposed GT v2.3 changes, for the Knowledge & Validation Engineer
- `review-log.md` — reviewer policy and pending sign-off

## Run the validator

```bash
cd /workspace/capstone-trackb/repo
.venv/bin/python validator/validate_spec.py
```

The virtualenv is not committed. Recreate it with:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`requirements.txt` lists `jsonschema`, `pandas` and `openpyxl`. The validator reads the GT workbook from the path above and never writes to it.

Do not call the inference endpoint from this repository. Do not read or echo `TRACKB_API_KEY`.
