"""Score the two Activity 3 pilot sheets without changing submitted labels."""
import argparse
from collections import Counter
import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil

import openpyxl

from score_activity3_pilot import CASES, FIELDS, TARGET, agreement, load_annotations

REPO = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def score(source, output, sheet_names):
    if output.exists():
        raise ValueError("Use a new output directory to preserve prior results")
    before = digest(source)
    vocabulary = json.loads((REPO / "vocab/controlled-vocabulary.json").read_text())
    template_path = REPO / "eval/activity-3-pilot/annotations.template.csv"
    with template_path.open(encoding="utf-8-sig", newline="") as stream:
        template = {row["pilot_id"]: row for row in csv.DictReader(stream)}
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    raw, normalized, formatting, inputs_changed, other_issues = {}, {}, [], [], []
    positions = {}
    try:
        for sheet_name in sheet_names:
            sheet = workbook[sheet_name]
            iterator = iter(sheet.iter_rows(values_only=True))
            headers = [str(value).strip() if value is not None else "" for value in next(iterator)]
            if not {"pilot_id", *FIELDS} <= set(headers):
                raise ValueError(f"{sheet_name}: required columns are missing")
            if len(set(headers)) != len(headers):
                raise ValueError(f"{sheet_name}: repeated or blank header")
            rows = {}
            normalized[sheet_name] = {}
            positions[sheet_name] = {}
            for row_number, values in enumerate(iterator, 2):
                if not any(value is not None and str(value).strip() for value in values):
                    continue
                row = dict(zip(headers, values))
                case = str(row.get("pilot_id") or "").strip()
                if case not in CASES or case in rows:
                    raise ValueError(f"{sheet_name}: invalid or repeated pilot ID {case!r}")
                rows[case] = row
                positions[sheet_name][case] = row_number
                labels = {"pilot_id": case}
                for field, key in FIELDS.items():
                    value = "" if row.get(field) is None else str(row[field])
                    options = {option.casefold(): option for option in vocabulary[key]}
                    canonical = options.get(value.strip().casefold())
                    if canonical is None:
                        raise ValueError(f"{sheet_name} {case}: missing or invalid {field} {value!r}")
                    labels[field] = canonical
                    if value != canonical:
                        formatting.append({"sheet": sheet_name, "pilot_id": case, "field": field,
                                           "cell": f"{openpyxl.utils.get_column_letter(headers.index(field) + 1)}{row_number}",
                                           "submitted": value, "scored": canonical,
                                           "reason": "Controlled-vocabulary casing and surrounding whitespace only"})
                normalized[sheet_name][case] = labels
                for field in ("split", "frozen_core", "query", "history", "known_facts"):
                    observed = str(row.get(field) or "").strip()
                    expected = str(template[case][field]).strip()
                    if field == "frozen_core":
                        observed, expected = observed.casefold(), expected.casefold()
                    if observed != expected:
                        inputs_changed.append({"sheet": sheet_name, "pilot_id": case, "field": field})
                bucket = str(row.get("bucket") or "").strip()
                if bucket and bucket not in {
                    "qualification", "interpretation", "docs", "history", "updates", "pricecompare",
                    "capabilitycompare", "coveragecompare", "limitscompare", "ownership",
                }:
                    other_issues.append({"sheet": sheet_name, "pilot_id": case, "field": "bucket",
                                         "value": bucket, "issue": "Outside the permitted bucket vocabulary; not scored"})
            if set(rows) != CASES:
                raise ValueError(f"{sheet_name}: missing pilot IDs {sorted(CASES - set(rows))}")
            raw[sheet_name] = rows
    finally:
        workbook.close()
    if inputs_changed:
        raise ValueError(f"Pilot inputs differ from the supplied packet: {inputs_changed}")
    if digest(source) != before:
        raise ValueError("The source workbook changed during reading; rerun after saving it")

    output.mkdir(parents=True)
    copied = output / "annotations.source.xlsx"
    shutil.copyfile(source, copied)
    if digest(copied) != before:
        raise ValueError("The source workbook changed before snapshot creation")
    exports = []
    for sheet_name in sheet_names:
        exported = output / f"{sheet_name}.csv"
        write_csv(exported, ["pilot_id", *FIELDS], [normalized[sheet_name][case] for case in sorted(CASES)])
        # Reuse the approved CSV validation path after formatting normalization.
        load_annotations(exported, vocabulary)
        exports.append(exported)

    scores, pairs, disagreements, review = [], [], [], []
    left_name, right_name = sheet_names
    for field in FIELDS:
        left = [normalized[left_name][case][field] for case in sorted(CASES)]
        right = [normalized[right_name][case][field] for case in sorted(CASES)]
        matches, kappa = agreement(left, right)
        n = len(left)
        # Independently verify the existing scorer from the contingency table.
        table = Counter(zip(left, right))
        labels = sorted(set(left) | set(right))
        chance = sum(Fraction(sum(table[a, b] for b in labels) * sum(table[b, a] for b in labels), n*n)
                     for a in labels)
        observed = Fraction(matches, n)
        independent = None if chance == 1 else (observed - chance) / (1 - chance)
        assert kappa == independent
        raw_left = [str(raw[left_name][case][field]) for case in sorted(CASES)]
        raw_right = [str(raw[right_name][case][field]) for case in sorted(CASES)]
        raw_matches, raw_kappa = agreement(raw_left, raw_right)
        scores.append({"field": field, "pairs": n, "matches": matches,
                       "observed_agreement": float(observed), "chance_agreement": float(chance),
                       "kappa": None if kappa is None else float(kappa),
                       "kappa_exact": None if kappa is None else str(kappa),
                       "threshold": float(TARGET), "passed": kappa is not None and kappa >= TARGET,
                       "left_counts": dict(Counter(left)), "right_counts": dict(Counter(right)),
                       "raw_exact_matches": raw_matches,
                       "raw_exact_kappa": None if raw_kappa is None else float(raw_kappa),
                       "confusion_matrix": {a: {b: table[a, b] for b in labels} for a in labels}})
    for case in sorted(CASES):
        differences = []
        for field in FIELDS:
            left, right = normalized[left_name][case][field], normalized[right_name][case][field]
            row = {"pilot_id": case, "field": field, "Update_A": left, "Update_P": right, "agree": left == right}
            pairs.append(row)
            if left != right:
                disagreements.append(row)
                differences.append(field)
        if differences:
            review.append({"pilot_id": case, "query": raw[left_name][case]["query"],
                           "history": raw[left_name][case]["history"],
                           **{f"{field}_{suffix}": normalized[name][case][field]
                              for field in FIELDS for name, suffix in [(left_name, "A"), (right_name, "P")]},
                           **{f"final_{field}": "" for field in FIELDS}, "rationale": ""})
    write_csv(output / "pair-comparison.csv", ["pilot_id", "field", "Update_A", "Update_P", "agree"], pairs)
    write_csv(output / "disagreements.csv", ["pilot_id", "field", "Update_A", "Update_P", "agree"], disagreements)
    write_csv(output / "adjudication.template.csv", ["pilot_id", "query", "history",
              *[f"{field}_{suffix}" for field in FIELDS for suffix in ["A", "P"]],
              *[f"final_{field}" for field in FIELDS], "rationale"], review)
    result = {"source": str(source), "source_sha256": before, "sheets": sheet_names,
              "pilot_cases": len(CASES), "scored_fields": list(FIELDS),
              "input_differences": inputs_changed, "missing_or_unpaired_cases": [],
              "formatting_normalizations": formatting, "scores": scores,
              "agreement_criterion_passed": all(row["passed"] for row in scores),
              "disagreements": disagreements, "other_field_issues": other_issues,
              "gold_changed": False, "adjudication_applied": False,
              "method": "Unweighted Cohen kappa per field; (observed - chance)/(1 - chance)",
              "scope": "The labeling guide specifies intent, API and team for the agreement pilot. Other columns are not scored."}
    (output / "scores.json").write_text(json.dumps(result, indent=2) + "\n")
    body = ["# Activity 3 — Two-annotator pilot agreement", "",
            "Compared Update_A and Update_P from the supplied workbook. All ten cases P01–P10 are present exactly once in each sheet. Query, history, known facts and dataset membership match the original pilot packet. No missing labels or unmatched cases were excluded.", "",
            "The agreed pilot measures intent, API and team separately, with a target of κ ≥ 0.70 for every field.", "",
            "| Field | Exact agreement | Observed agreement | Chance agreement | Cohen’s κ | Target | Result |",
            "|---|---:|---:|---:|---:|---:|---|"]
    for row in scores:
        display = "undefined" if row["kappa"] is None else f"{row['kappa']:.4f}"
        body.append(f"| {row['field']} | {row['matches']}/{row['pairs']} | {row['observed_agreement']:.0%} | {row['chance_agreement']:.0%} | {display} | ≥0.70 | {'Pass' if row['passed'] else 'Re-pilot'} |")
    body += ["", "## Formatting only", "",
             "The scoring exports use controlled-vocabulary casing and trim surrounding whitespace. Submitted workbook cells remain unchanged.", ""]
    for item in formatting:
        body.append(f"- {item['sheet']}!{item['cell']}: `{item['submitted']}` → `{item['scored']}`.")
    team = next(row for row in scores if row["field"] == "team")
    raw_team = "undefined" if team["raw_exact_kappa"] is None else f"{team['raw_exact_kappa']:.4f}"
    body += ["", f"Without formatting normalization, team agreement is {team['raw_exact_matches']}/10 and κ={raw_team}. `sales` and `Sales` denote the same permitted team, so the normalized result is used.",
             "", "## Label disagreements retained for adjudication", "",
             "| Case | Field | Update_A | Update_P |", "|---|---|---|---|"]
    for row in disagreements:
        body.append(f"| {row['pilot_id']} | {row['field']} | {row['Update_A']} | {row['Update_P']} |")
    body += ["", "No semantic labels were changed or adjudicated. The reported κ uses the original independent decisions, after formatting-only normalization. Save any later consensus in adjudication.template.csv separately; do not replace the original submissions or recompute initial agreement on consensus labels.",
             "", "## Scope and next step", "",
             "The Activity 3 annotation-agreement criterion passes for all three required fields. Confirm the final labels for P08 and P10 in the separate adjudication file before promoting a consensus annotation. High agreement measures consistency between annotators; it does not establish factual correctness or complete gold-record validation.",
             "", "Other review fields remain outside this agreement score. Update_A P01 has bucket `capability_question`, which is not an allowed bucket. The sheets also differ on the P09 and P10 buckets. Reference answers, citations, rubric, escalation and tool expectations still require their own completeness/evidence checks. Missing optional review fields were not counted as agreement.",
             "", "## Reproduce", "", "```bash",
             "python eval/score_activity3_workbook.py --workbook /path/to/annotation-2-members.xlsx --output /path/to/new-results",
             "python3 eval/score_activity3_workbook.py --workbook /path/to/annotation-2-members.xlsx --output /path/to/new-results",
             "```", "", "Use either command in the activated project environment. The output directory must be new. The exports can also be checked with the existing CSV scorer:", "", "```bash",
             "python eval/score_activity3_pilot.py eval/activity-3-pilot/results/annotation-agreement/Update_A.csv eval/activity-3-pilot/results/annotation-agreement/Update_P.csv",
             "python3 eval/score_activity3_pilot.py eval/activity-3-pilot/results/annotation-agreement/Update_A.csv eval/activity-3-pilot/results/annotation-agreement/Update_P.csv",
             "```", "", "## Evidence", "",
             "The source workbook is preserved byte-for-byte in annotations.source.xlsx. Update_A.csv and Update_P.csv contain only the four pilot scoring columns. scores.json includes marginals, chance agreement and confusion matrices. pair-comparison.csv records all 30 comparisons; disagreements.csv and adjudication.template.csv retain the unresolved decisions.", "",
             f"Source SHA-256: `{before}`. Frozen GT was not changed. No model, inference endpoint or holdout cases were used.", ""]
    (output / "report.md").write_text("\n".join(body))
    manifest = {"workbook_sha256": before, "source_unchanged": digest(source) == before,
                "sheets": sheet_names, "pilot_template_sha256": digest(template_path),
                "scorer_sha256": digest(Path(__file__)),
                "legacy_scorer_sha256": digest(REPO / "eval/score_activity3_pilot.py"),
                "vocabulary_sha256": digest(REPO / "vocab/controlled-vocabulary.json"),
                "artifacts": {p.name: digest(p) for p in output.iterdir() if p.is_file()}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"agreement_criterion_passed": result["agreement_criterion_passed"],
                      "scores": [{key: row[key] for key in ["field", "pairs", "matches", "kappa", "passed"]} for row in scores]}, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = score(args.workbook, args.output, ["Update_A", "Update_P"])
    raise SystemExit(0 if result["agreement_criterion_passed"] else 1)
