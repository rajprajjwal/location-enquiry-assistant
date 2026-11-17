"""Score Activity 2 interpretation predictions against manifest-pinned gold offline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import string
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(REPO))

from copilot.validation.rules import canonical_provider, validate_interpretation_output
from mapping.map_gt import _parse_volume_number


LABELS = ("intent", "api", "team")
FREE_TEXT_FIELDS = ("timeline", "budget", "technical_constraints", "decision_maker")
SLOTS = ("use_case_api", "region", "monthly_volume", "current_provider", *FREE_TEXT_FIELDS)
REGION_ALIASES = {"india", "indian", "pan-india", "in"}
THRESHOLDS = {
    "intent_acc": 0.90,
    "api_acc": 0.95,
    "qual_f1": 0.85,
    "missing_recall": 0.85,
    "schema_valid_rate": 1.00,
}
PROVIDER_PUNCTUATION = string.punctuation.replace("(", "").replace(")", "")


def index_jsonl(text: str, source: str, expected_ids: set[str]) -> dict[str, dict]:
    records = {}
    for line_number, line in enumerate(text.split("\n"), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{source}, line {line_number}: {exc.msg}") from exc
        record_id = row.get("record_id") if isinstance(row, dict) else None
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError(f"{source}, line {line_number}: a nonempty record_id is required")
        if record_id in records:
            raise ValueError(f"{source}: duplicate record_id {record_id}")
        records[record_id] = row

    missing = sorted(expected_ids - records.keys())
    extra = sorted(records.keys() - expected_ids)
    if missing or extra:
        raise ValueError(f"{source}: record IDs differ from manifest (missing={missing}, extra={extra})")
    return records


def normalize_text(value: str | None, punctuation: str = string.punctuation) -> str | None:
    if value is None:
        return None
    text = " ".join(unicodedata.normalize("NFKC", value).casefold().split())
    text = text.strip(punctuation + " ")
    return None if text in {"", "n/a", "unknown", "none"} else text


def normalize_slot(field: str, value):
    if value is None:
        return None
    if field == "use_case_api":
        return value["api"]
    if field == "monthly_volume":
        raw = normalize_text(value["raw"])
        number = value.get("requests_per_month")
        if number is None and raw is not None:
            number = _parse_volume_number(raw)
        if raw is None and number is None:
            return None
        return {"requests_per_month": number, "raw": raw}
    text = normalize_text(value)
    if field == "region" and text in REGION_ALIASES:
        return "India"
    if field == "current_provider":
        return canonical_provider(normalize_text(value, PROVIDER_PUNCTUATION)) or text
    return text


def matches(field: str, gold, predicted) -> bool:
    if field == "monthly_volume":
        numbers = gold["requests_per_month"], predicted["requests_per_month"]
        if all(number is not None for number in numbers):
            return numbers[0] == numbers[1]
        return gold["raw"] is not None and gold["raw"] == predicted["raw"]
    if field in FREE_TEXT_FIELDS:
        short, long = sorted((gold, predicted), key=len)
        return short == long or (len(short) >= 3 and short in long)
    return gold == predicted


def compare_slot(field: str, gold, predicted) -> dict:
    gold = normalize_slot(field, gold)
    predicted = normalize_slot(field, predicted)
    matched = gold is not None and predicted is not None and matches(field, gold, predicted)
    return {
        "gold": gold,
        "predicted": predicted,
        "tp": int(matched),
        "fp": int(predicted is not None and not matched),
        "fn": int(gold is not None and not matched),
    }


def score_record(gold: dict, prediction: dict) -> dict:
    # record_id belongs to the JSONL envelope, rather than the output contract.
    output = {key: value for key, value in prediction.items() if key != "record_id"}
    errors = validate_interpretation_output(output)
    valid = not errors
    abstain = output.get("abstain") is True
    expected = gold["outputs"]["qualification_details"]
    # Keep invalid records in every denominator and award no credit for their output fields.
    qualification = output["qualification_details"] if valid else {}
    missing_gold = set(expected["missing_required_fields"])
    missing_predicted = set(output["missing_required_fields"]) if valid else set()
    trace = output["trace"] if valid else {}

    return {
        "record_id": gold["record_id"],
        "bucket": gold["bucket"],
        "labels": {
            field: {
                "gold": gold[field],
                "predicted": output.get(field) if valid else None,
                "correct": valid and not abstain and output[field] is not None and output[field] == gold[field],
            }
            for field in LABELS
        },
        "qualification": {field: compare_slot(field, expected[field], qualification.get(field)) for field in SLOTS},
        "use_case_text": compare_slot(
            "use_case", (expected.get("use_case_api") or {}).get("use_case"),
            (qualification.get("use_case_api") or {}).get("use_case"),
        ),
        "missing_fields": {
            "gold": sorted(missing_gold),
            "predicted": sorted(missing_predicted),
            "matched": len(missing_gold & missing_predicted),
        },
        "schema_valid": valid,
        "validation_errors": errors,
        "abstain": abstain,
        "abstain_reason": output.get("abstain_reason") if valid else None,
        "repair_attempts": trace.get("repair_attempts"),
        "model_calls": trace.get("model_calls"),
        "prompt_version": trace.get("prompt_version"),
    }


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def detection_metrics(slots) -> dict:
    tp = fp = fn = 0
    for slot in slots:
        tp += slot["tp"]
        fp += slot["fp"]
        fn += slot["fn"]
    denominator = 2 * tp + fp + fn
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "f1": ratio(2 * tp, denominator) if denominator else 1.0,
    }


def summarize(records: list[dict]) -> dict:
    count = len(records)
    missing = [record["missing_fields"] for record in records]
    missing_hits = sum(item["matched"] for item in missing)
    qualification = detection_metrics(slot for row in records for slot in row["qualification"].values())
    qualification_without_api = detection_metrics(
        slot for row in records for field, slot in row["qualification"].items() if field != "use_case_api"
    )
    return {
        "records": count,
        **{f"{field}_acc": ratio(sum(row["labels"][field]["correct"] for row in records), count) for field in LABELS},
        "qual_f1": qualification["f1"],
        "qual_f1_excl_api": qualification_without_api["f1"],
        "per_slot": {field: detection_metrics(row["qualification"][field] for row in records) for field in SLOTS},
        "use_case_text": detection_metrics(row["use_case_text"] for row in records),
        "missing_recall": ratio(missing_hits, sum(len(item["gold"]) for item in missing)),
        "missing_precision": ratio(missing_hits, sum(len(item["predicted"]) for item in missing)),
        "schema_valid_rate": ratio(sum(row["schema_valid"] for row in records), count),
        "abstain_rate": ratio(sum(row["abstain"] for row in records), count),
        "model_calls": sum(row["model_calls"] or 0 for row in records),
        "repair_rate": ratio(sum(bool(row["repair_attempts"]) for row in records), count),
    }


def verify_reviews(path: Path | None, gold: dict, gold_sha256: str) -> None:
    if path is None:
        raise ValueError("development scoring requires the completed review CSV (--reviews)")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"record_id", "review_status", "reviewer", "review_date", "second_review_date",
                    "second_review_evidence", "gold_sha256"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("review CSV is missing required columns")
        reviewed = set()
        pending = 0
        for row in reader:
            record_id = row["record_id"]
            if record_id not in gold or record_id in reviewed:
                raise ValueError(f"review CSV has an unexpected or duplicate ID: {record_id}")
            if row["gold_sha256"] != gold_sha256:
                raise ValueError(f"{record_id}: review is for a different gold SHA-256")
            reviewed.add(record_id)
            fields = ["reviewer", "review_date"]
            if gold[record_id]["review_priority"] == "high":
                fields.extend(["second_review_date", "second_review_evidence"])
            approved = (row["review_status"] or "").strip().casefold() == "approved"
            if not approved or not all((row[key] or "").strip() for key in fields):
                pending += 1
    incomplete = pending + len(gold.keys() - reviewed)
    if incomplete:
        raise ValueError(f"development gold review incomplete: {len(gold) - incomplete}/{len(gold)} approved")


def load_gold(gold_path: Path, manifest_path: Path, mode: str, reviews_path: Path | None,
              *, allow_unreviewed: bool = False):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("mode", "frozen") != mode:
        raise ValueError("scoring mode does not match the manifest")
    development = mode == "development"
    if allow_unreviewed and not development:
        raise ValueError("--allow-unreviewed is only available in development mode")
    id_key, file_key = ("record_ids", "gold_file") if development else ("frozen_record_ids", "frozen_file")
    ids = manifest[id_key]
    if not isinstance(ids, list) or not ids or any(
        not isinstance(record_id, str) or not record_id.strip() for record_id in ids
    ):
        raise ValueError(f"manifest {id_key} must be a nonempty list of record IDs")
    if len(set(ids)) != len(ids) or len(ids) != manifest[file_key]["records"]:
        raise ValueError("manifest IDs contain duplicates or disagree with the recorded count")

    gold_bytes = gold_path.read_bytes()
    gold_sha256 = hashlib.sha256(gold_bytes).hexdigest()
    if gold_sha256 != manifest[file_key]["sha256"]:
        raise ValueError("gold SHA-256 does not match the manifest")
    expected_ids = set(ids)
    gold = index_jsonl(gold_bytes.decode("utf-8"), "gold", expected_ids)
    required_frozen = not development
    for record_id, expected in gold.items():
        if expected.get("split") != "eval" or expected.get("frozen_core") is not required_frozen:
            raise ValueError(f"{record_id}: gold is not marked as a {mode} eval record")
    if development:
        if expected_ids.intersection(manifest["excluded_record_ids"]):
            raise ValueError("development manifest includes frozen or few-shot example IDs")
        excluded_families = set(manifest["excluded_template_families"])
        if any(row["template_family"] in excluded_families for row in gold.values()):
            raise ValueError("development gold includes excluded template families")
        if any(row["verification_status"] != "verified_live" for row in gold.values()):
            raise ValueError("development gold includes unverified records")
        if not allow_unreviewed:
            verify_reviews(reviews_path, gold, gold_sha256)
    return manifest, ids, gold, gold_sha256


def score_activity2(predictions_path: Path, gold_path: Path, manifest_path: Path, git_commit: str | None,
                    *, mode: str = "frozen", reviews_path: Path | None = None, allow_unreviewed: bool = False):
    manifest, ids, gold, gold_sha256 = load_gold(
        gold_path, manifest_path, mode, reviews_path, allow_unreviewed=allow_unreviewed
    )
    predictions = index_jsonl(predictions_path.read_text(encoding="utf-8"), "predictions", set(ids))

    records = []
    groups = {name: defaultdict(list) for name in ("bucket", "api", "team")}
    for record_id in ids:
        expected = gold[record_id]
        row = score_record(expected, predictions[record_id])
        records.append(row)
        for name, grouped in groups.items():
            grouped[expected[name]].append(row)

    scores = summarize(records)
    gates = {metric: scores[metric] >= minimum for metric, minimum in THRESHOLDS.items()}
    versions = sorted({row["prompt_version"] for row in records if row["prompt_version"]})
    scores.update(
        evaluation_mode=mode, thresholds=THRESHOLDS, gates=gates,
        passed=all(gates.values()) if mode == "frozen" else None,
        manifest_version=manifest["manifest_version"], gold_sha256=gold_sha256,
        prompt_version=versions[0] if len(versions) == 1 else None, prompt_versions=versions,
        git_commit=git_commit,
        breakdowns={name: {key: summarize(rows) for key, rows in sorted(grouped.items())}
                    for name, grouped in groups.items()},
    )
    if mode == "development":
        scores.update(provisional=allow_unreviewed, human_gold_review="skipped" if allow_unreviewed else "complete")
    return scores, records


def render_report(scores: dict) -> str:
    lines = ["# Activity 2 interpretation scoring", "", f"Cases scored: {scores['records']}", "",
             f"Evaluation mode: {scores['evaluation_mode']}", ""]
    if scores.get("provisional"):
        lines.extend(["**Provisional development metrics.** Human review of the expected labels was skipped.", ""])
    heading = "Acceptance metric" if scores["evaluation_mode"] == "frozen" else "Reference metric (frozen targets)"
    lines.extend([f"| {heading} | Actual | Minimum | Result |", "|---|---:|---:|---|"])
    for metric, minimum in THRESHOLDS.items():
        result = "PASS" if scores["gates"][metric] else "FAIL"
        lines.append(f"| {metric} | {scores[metric]:.4f} | {minimum:.4f} | {result} |")
    lines.extend([
        "", f"Abstain rate: {scores['abstain_rate']:.4f}. Repair rate: {scores['repair_rate']:.4f}.",
        f"Team accuracy: {scores['team_acc']:.4f}. "
        f"Qualification F1 excluding `use_case_api`: {scores['qual_f1_excl_api']:.4f}. "
        f"Missing-field precision: {scores['missing_precision']:.4f}.",
    ])
    for group, rows in scores["breakdowns"].items():
        lines.extend([
            "", f"## By {group}", "",
            f"| {group.title()} | Cases | Intent accuracy | API accuracy | Team accuracy | Qualification F1 | Missing recall |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ])
        for key, metrics in rows.items():
            lines.append(f"| {key} | {metrics['records']} | {metrics['intent_acc']:.4f} | {metrics['api_acc']:.4f} | "
                         f"{metrics['team_acc']:.4f} | {metrics['qual_f1']:.4f} | {metrics['missing_recall']:.4f} |")
    return "\n".join(lines) + "\n"


def round_metrics(value):
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {key: round_metrics(item) for key, item in value.items()}
    return value


def checkout_commit() -> str | None:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("frozen", "development"), default="frozen")
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--reviews", type=Path, help="completed development review CSV")
    parser.add_argument("--allow-unreviewed", action="store_true",
                        help="generate provisional development metrics with source-verified, unreviewed gold")
    parser.add_argument("--check-ready", action="store_true", help="validate development inputs, gold and reviews offline")
    parser.add_argument("--inputs", type=Path, help="development input JSONL for --check-ready")
    parser.add_argument("--git-commit", help="inference commit when known (otherwise records the scorer checkout HEAD)")
    args = parser.parse_args(argv)

    try:
        if args.allow_unreviewed and args.reviews is not None:
            raise ValueError("choose either --reviews or --allow-unreviewed")
        if args.check_ready:
            if args.mode != "development" or args.inputs is None:
                raise ValueError("--check-ready requires --mode development and --inputs")
            manifest, ids, _, _ = load_gold(
                args.gold, args.manifest, args.mode, args.reviews, allow_unreviewed=args.allow_unreviewed
            )
            if hashlib.sha256(args.inputs.read_bytes()).hexdigest() != manifest["inputs_file"]["sha256"]:
                raise ValueError("input JSONL SHA-256 does not match the development manifest")
            status = "provisional, human review skipped" if args.allow_unreviewed else "human review complete"
            print(f"Ready for development inference: {len(ids)} inputs ({status}).")
            return 0
        if args.predictions is None or args.out is None:
            raise ValueError("scoring requires --predictions and --out")
        input_paths = {path.resolve() for path in (args.predictions, args.gold, args.manifest, args.reviews) if path}
        output_paths = [args.out / name for name in ("scores.json", "per_record.jsonl", "report.md")]
        if any(path.resolve() in input_paths for path in output_paths):
            raise ValueError("report paths must differ from all input paths")
        scores, records = score_activity2(
            args.predictions, args.gold, args.manifest, args.git_commit or checkout_commit(),
            mode=args.mode, reviews_path=args.reviews, allow_unreviewed=args.allow_unreviewed,
        )
        scores["git_commit_source"] = "inference_run" if args.git_commit else "scorer_checkout"
        args.out.mkdir(parents=True, exist_ok=True)
        scores_path, records_path, report_path = output_paths
        records_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records), encoding="utf-8"
        )
        report_path.write_text(render_report(scores), encoding="utf-8")
        scores_path.write_text(json.dumps(round_metrics(scores), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    except (KeyError, OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    status = "PASS" if scores["passed"] else "FAIL"
    label = f"Acceptance: {status}." if args.mode == "frozen" else "Development metrics."
    if args.allow_unreviewed:
        label = "Provisional development metrics."
    print(f"Scored {scores['records']} cases offline. {label} Reports: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
