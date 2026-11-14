#!/usr/bin/env python3
"""Compare interpretation validation with the dataset validator on GT v2.5.

Purpose: report where the new qualification checks disagree with
``validator/validate_spec.py`` on the 532 committed gold envelopes.
Use case: read-only evidence, including the holdout split. No tuning.
Example: ``python scripts/crosscheck_interpretation_validation.py``

The GT workbook is not required. The committed gold JSONL is the record
set. This script does not write gold, schemas, or the dataset validator.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pydantic import ValidationError  # noqa: E402

from copilot.models import QualificationDetails  # noqa: E402
from copilot.validation.rules import (  # noqa: E402
    _schema_errors,
    validate_qualification,
)
from validator.validate_spec import (  # noqa: E402
    load_schemas,
    required_field_violations,
    validator_for,
)

GOLD = REPO / "mapping" / "gold_outputs_all.jsonl"
REPORT = REPO / "docs" / "interpretation-validation-crosscheck.md"
CONSISTENCY = {"MISSING_REQUIRED_FIELDS", "COMPLETE_FLAG"}


def _code(error: str) -> str:
    _pointer, code, _detail = error.split(": ", 2)
    return code


def _schema_only(errors: list[str]) -> list[str]:
    return [error for error in errors if _code(error) not in CONSISTENCY]


def _verdict(ok: bool) -> str:
    return "pass" if ok else "fail"


def _load_records() -> list[dict]:
    records = []
    for line in GOLD.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _api_equal(record: dict) -> bool:
    qual = record["outputs"]["qualification_details"]
    use_case_api = qual.get("use_case_api") if isinstance(qual, dict) else None
    if not isinstance(use_case_api, dict):
        return False
    return use_case_api.get("api") == record.get("api")


def main() -> int:
    records = _load_records()
    if len(records) != 532:
        print(f"expected 532 gold records, found {len(records)}", file=sys.stderr)
        return 1

    schemas, registry, schema_file_errors = load_schemas()
    if schema_file_errors:
        print("dataset schema self-check failed:", schema_file_errors, file=sys.stderr)
        return 1
    dataset_validator = validator_for(schemas["qualification_details.schema.json"], registry)
    vocab = json.loads((REPO / "vocab" / "controlled-vocabulary.json").read_text(encoding="utf-8"))

    differences: list[dict[str, str]] = []
    pydantic_failures: list[str] = []
    split_counts: dict[str, int] = {}
    dataset_pass = 0
    interpretation_pass = 0
    field_agree = {
        "schema": 0,
        "missing_required_fields": 0,
        "complete": 0,
        "use_case_api.api": 0,
    }

    for record in records:
        split_counts[str(record.get("split"))] = split_counts.get(str(record.get("split")), 0) + 1
        qual = record["outputs"]["qualification_details"]
        record_id = str(record["record_id"])
        our_errors = validate_qualification(qual)
        our_schema = _schema_only(our_errors)
        dataset_schema = _schema_errors(qual, dataset_validator)
        dataset_consistency = required_field_violations(
            {"outputs": {"qualification_details": qual}},
            vocab,
        )
        dataset_missing_ok = not any(
            item.startswith("missing_required_fields_inconsistent:")
            for item in dataset_consistency
        )
        dataset_complete_ok = not any(
            item.startswith("complete_flag_inconsistent:") for item in dataset_consistency
        )
        our_missing_ok = not any(_code(item) == "MISSING_REQUIRED_FIELDS" for item in our_errors)
        our_complete_ok = not any(_code(item) == "COMPLETE_FLAG" for item in our_errors)
        dataset_api_ok = True  # the dataset validator has no api-equality rule
        our_api_ok = _api_equal(record)
        if not dataset_schema and dataset_missing_ok and dataset_complete_ok:
            dataset_pass += 1
        if not our_errors and our_api_ok:
            interpretation_pass += 1

        checks = {
            "schema": (
                dataset_schema == our_schema,
                "pass" if not dataset_schema else "fail: " + " | ".join(dataset_schema),
                "pass" if not our_schema else "fail: " + " | ".join(our_schema),
            ),
            "missing_required_fields": (
                dataset_missing_ok == our_missing_ok,
                _verdict(dataset_missing_ok),
                _verdict(our_missing_ok),
            ),
            "complete": (
                dataset_complete_ok == our_complete_ok,
                _verdict(dataset_complete_ok),
                _verdict(our_complete_ok),
            ),
            "use_case_api.api": (
                dataset_api_ok == our_api_ok,
                "pass (no separate dataset rule; record accepted)",
                _verdict(our_api_ok),
            ),
        }
        for field, (agree, dataset_verdict, our_verdict) in checks.items():
            if agree:
                field_agree[field] += 1
                continue
            differences.append(
                {
                    "record_id": record_id,
                    "field": field,
                    "dataset_verdict": dataset_verdict,
                    "interpretation_validation_verdict": our_verdict,
                }
            )

        try:
            QualificationDetails.model_validate(qual)
        except ValidationError as exc:
            pydantic_failures.append(f"{record_id}: {exc.error_count()} validation error(s)")

    matched = len(records) - len({row["record_id"] for row in differences})
    digest = hashlib.sha256(GOLD.read_bytes()).hexdigest()
    lines = [
        "# Interpretation validation cross-check",
        "",
        "Read-only comparison of the 532 committed GT v2.5 gold envelopes",
        f"(`mapping/gold_outputs_all.jsonl`, sha256 `{digest}`).",
        "Holdout rows were read and not used to change rules, schemas, or tests.",
        "No provider API was called. The dataset validator and the gold files",
        "were not modified.",
        "",
        "Dataset side: `validator.validate_spec.load_schemas`, `validator_for`,",
        "and `required_field_violations` on `outputs.qualification_details`.",
        "`validate_spec.py` was not executed as a program: that entry point",
        "rewrites gold outputs, the vocabulary diff, and the validator report.",
        "",
        "New side: `copilot.validation.rules.validate_qualification`, plus",
        "`use_case_api.api` compared with the envelope `api` (the check",
        "`validate_interpretation_output` reports as `API_MISMATCH`).",
        "The dataset validator does not have that rule; a record is a",
        "difference on this field only when the new check fails.",
        "",
        "Schema errors on both sides are formatted by the same pointer",
        "function. A schema difference is either a different pass/fail or",
        "a different error list. `missing_required_fields` is order-sensitive",
        "in the new check and sorted in the dataset check. `complete` must",
        "be the boolean `True` or `False` in the new check; the dataset",
        "check uses `bool(complete)`.",
        "",
        "## Match count",
        "",
        f"**{matched}/{len(records)}** records agree on every compared field.",
        "",
        f"Dataset qualification checks passed **{dataset_pass}/{len(records)}**.",
        f"Interpretation qualification checks passed **{interpretation_pass}/{len(records)}** "
        "(schema, missing-field list, complete flag, and `use_case_api.api`).",
        "",
        "| Field | Records in agreement |",
        "| --- | --- |",
    ]
    for field, count in field_agree.items():
        lines.append(f"| `{field}` | {count}/{len(records)} |")
    lines += [
        "",
        f"Splits read: {json.dumps(split_counts, sort_keys=True)}.",
        "",
        "## Differences",
        "",
    ]
    if not differences:
        lines.append("None.")
    else:
        for row in differences:
            lines.append(
                f"- record_id: `{row['record_id']}`"
            )
            lines.append(f"  - field: `{row['field']}`")
            lines.append(f"  - dataset_verdict: {row['dataset_verdict']}")
            lines.append(
                "  - interpretation_validation_verdict: "
                f"{row['interpretation_validation_verdict']}"
            )
    lines += [
        "",
        "## Generated QualificationDetails",
        "",
        f"Pydantic `QualificationDetails.model_validate` accepted "
        f"**{len(records) - len(pydantic_failures)}/{len(records)}** "
        "qualification objects.",
        "",
    ]
    if pydantic_failures:
        lines.append("Failures:")
        lines.append("")
        for item in pydantic_failures:
            lines.append(f"- {item}")
    else:
        lines.append("No model failures.")
    lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"match_count={matched}/{len(records)}")
    print(f"differences={len(differences)}")
    print(f"pydantic_failures={len(pydantic_failures)}")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
