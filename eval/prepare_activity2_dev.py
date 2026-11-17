"""Prepare a balanced, reviewable 80-case Activity 2 development bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from openpyxl import load_workbook

REPO = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(REPO))

from copilot.interpret.gt_adapter import from_gt_question, write_inputs
from copilot.models import InterpretationInput


APIS = ("autocomplete", "directions", "distance_matrix", "reverse_geocode")
TEAMS = ("Sales", "Support")
PER_API = 20
NEAR_DUPLICATE_THRESHOLD = 0.90
REVIEW_FIELDS = (
    "record_id", "api", "team", "intent", "bucket", "question", "expected_qualification",
    "expected_missing_fields", "review_priority", "review_status", "reviewer", "review_date",
    "review_notes", "second_review_date", "second_review_evidence", "gold_sha256",
)


def grams(question: str) -> frozenset[str]:
    normalized = " ".join(re.findall(r"\w+", question.casefold()))
    return frozenset(normalized[i:i + 4] for i in range(max(1, len(normalized) - 3)))


def near_duplicate(left: frozenset[str], right: frozenset[str]) -> bool:
    return len(left & right) / len(left | right) >= NEAR_DUPLICATE_THRESHOLD


def sales_quotas(available: Counter) -> dict[str, int]:
    bounds = {
        api: (max(0, PER_API - available[api, "Support"]), min(PER_API, available[api, "Sales"]))
        for api in APIS
    }
    if any(low > high for low, high in bounds.values()):
        raise ValueError("at least one API has fewer than 20 eligible development cases")
    quotas = {api: min(high, max(low, PER_API // 2)) for api, (low, high) in bounds.items()}
    target = PER_API * len(APIS) // 2
    while sum(quotas.values()) != target:
        direction = 1 if sum(quotas.values()) < target else -1
        adjustable = [api for api, (low, high) in bounds.items() if low <= quotas[api] + direction <= high]
        if not adjustable:
            raise ValueError("eligible cases cannot support a 40 Sales / 40 Support split")
        api = min(adjustable, key=lambda item: (abs(quotas[item] + direction - PER_API / 2), item))
        quotas[api] += direction
    return quotas


def select_cases(rows: dict, excluded_ids: set[str]) -> tuple[list[dict], set[str], dict]:
    missing = excluded_ids - rows.keys()
    if missing:
        raise ValueError(f"exclusion IDs missing from eval workbook: {', '.join(sorted(missing))}")
    excluded_families = {rows[record_id]["template_family"] for record_id in excluded_ids}
    excluded_text = [grams(rows[record_id]["question"]) for record_id in sorted(excluded_ids)]
    eligible = []
    lexical_exclusions = 0
    for row in rows.values():
        if row["frozen_core"] or row["id"] in excluded_ids or row["template_family"] in excluded_families:
            continue
        if row["verification_status"] != "verified_live" or row["api"] not in APIS or row["team"] not in TEAMS:
            continue
        signature = grams(row["question"])
        if any(near_duplicate(signature, other) for other in excluded_text):
            lexical_exclusions += 1
            continue
        eligible.append((row, signature))

    # Deduplicate before setting quotas so unavailable duplicates cannot fill a stratum.
    distinct, signatures = [], []
    for row, signature in sorted(eligible, key=lambda item: (not item[0]["history"], item[0]["id"])):
        if not any(near_duplicate(signature, other) for other in signatures):
            distinct.append(row)
            signatures.append(signature)

    quotas = sales_quotas(Counter((row["api"], row["team"]) for row in distinct))
    selected = []
    by_bucket, by_family, by_intent = Counter(), Counter(), Counter()
    for api in APIS:
        for team in TEAMS:
            count = quotas[api] if team == "Sales" else PER_API - quotas[api]
            pool = [row for row in distinct if (row["api"], row["team"]) == (api, team)]
            for _ in range(count):
                row = min(pool, key=lambda item: (
                    not item["history"], by_family[item["template_family"]],
                    by_bucket[item["bucket"]], by_intent[item["intent"]], item["id"],
                ))
                pool.remove(row)
                selected.append(row)
                by_bucket[row["bucket"]] += 1
                by_family[row["template_family"]] += 1
                by_intent[row["intent"]] += 1
    selection = {"eligible": len(eligible), "lexical_exclusions": lexical_exclusions,
                 "within_pool_near_duplicates_removed": len(eligible) - len(distinct)}
    return selected, excluded_families, selection


def prepare(workbook_path: Path, mapped_gold_path: Path, freeze_path: Path, fewshot_paths: list[Path], out: Path) -> dict:
    freeze_bytes = freeze_path.read_bytes()
    freeze = json.loads(freeze_bytes)
    source = freeze["sources"]["gt_v2_5.xlsx"]
    workbook_sha256 = hashlib.sha256(workbook_path.read_bytes()).hexdigest()
    if workbook_sha256 != source["sha256"]:
        raise ValueError("workbook SHA-256 differs from the freeze manifest")
    mapped_bytes = mapped_gold_path.read_bytes()
    mapped_sha256 = hashlib.sha256(mapped_bytes).hexdigest()
    if mapped_sha256 != freeze["gold_all_file"]["sha256"]:
        raise ValueError("mapped gold SHA-256 differs from the freeze manifest")
    core_ids = set(freeze["frozen_record_ids"])
    fewshot_ids = set()
    for path in fewshot_paths:
        examples = json.loads(path.read_text(encoding="utf-8"))
        fewshot_ids.update(examples["record_ids"] if isinstance(examples, dict) else examples)

    mapped = {}
    for line in mapped_bytes.split(b"\n"):
        if line.strip():
            record = json.loads(line)
            if record["split"] == "eval":
                mapped[record["record_id"]] = record

    rows = {}
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        values = workbook[source["sheet"]].values
        headers = next(values)
        split_column = headers.index("split")
        for values_row in values:
            if values_row[split_column] != "eval":
                continue
            row = dict(zip(headers, values_row))
            record_id = row["id"]
            label = mapped[record_id]
            if row["frozen_core"] != label["frozen_core"] or row["frozen_core"] != (record_id in core_ids):
                raise ValueError(f"{record_id}: frozen membership disagrees across sources")
            if record_id in rows:
                raise ValueError(f"duplicate eval workbook ID: {record_id}")
            query, history = from_gt_question(row["question"])
            rows[record_id] = {**row, "query": query, "history": history,
                               "api": label["api"], "team": label["team"], "intent": label["intent"]}
    finally:
        workbook.close()

    selected, excluded_families, stats = select_cases(rows, core_ids | fewshot_ids)
    inputs = [InterpretationInput(record_id=row["id"], query=row["query"], history=row["history"], known_facts=[])
              for row in selected]
    gold = []
    for row in selected:
        envelope = mapped[row["id"]]
        gold.append({
            **{key: envelope[key] for key in ("record_id", "api", "team", "intent", "bucket", "split", "frozen_core")},
            **{key: row[key] for key in ("template_family", "verification_status", "review_priority")},
            "outputs": {"qualification_details": envelope["outputs"]["qualification_details"]},
        })
    gold_bytes = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in gold).encode("utf-8")
    gold_sha256 = hashlib.sha256(gold_bytes).hexdigest()

    out.mkdir(parents=True, exist_ok=True)
    inputs_path = out / "inputs.jsonl"
    write_inputs(inputs_path, inputs)
    (out / "gold.jsonl").write_bytes(gold_bytes)
    with (out / "review.csv").open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        for row, expected in zip(selected, gold):
            qual = expected["outputs"]["qualification_details"]
            question = row["question"]
            if question.lstrip().startswith(("=", "+", "-", "@")):
                question = "'" + question
            writer.writerow({
                **{key: expected[key] for key in ("record_id", "api", "team", "intent", "bucket", "review_priority")},
                "question": question,
                "expected_qualification": json.dumps({key: value for key, value in qual.items()
                                                        if key not in {"missing_required_fields", "complete"}}, ensure_ascii=False),
                "expected_missing_fields": ", ".join(qual["missing_required_fields"]),
                "review_status": "pending", "gold_sha256": gold_sha256,
            })

    manifest = {
        "manifest_version": 1, "mode": "development", "record_ids": [row["record_id"] for row in gold],
        "gold_file": {"sha256": gold_sha256, "records": len(gold)},
        "inputs_file": {"sha256": hashlib.sha256(inputs_path.read_bytes()).hexdigest(), "records": len(inputs)},
        "source_workbook_sha256": workbook_sha256, "source_mapped_gold_sha256": mapped_sha256,
        "source_freeze_sha256": hashlib.sha256(freeze_bytes).hexdigest(),
        "excluded_record_ids": sorted(core_ids | fewshot_ids), "excluded_template_families": sorted(excluded_families),
        "selection": {
            **stats, "by_api": dict(Counter(row["api"] for row in gold)), "by_team": dict(Counter(row["team"] for row in gold)),
            "by_bucket": dict(Counter(row["bucket"] for row in gold)), "with_history": sum(bool(item.history) for item in inputs),
            "lexical_check": {"metric": "normalized character 4-gram Jaccard", "threshold": NEAR_DUPLICATE_THRESHOLD},
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", required=True, type=Path)
    parser.add_argument("--gold", type=Path, default=REPO / "mapping" / "gold_outputs_all.jsonl")
    parser.add_argument("--freeze-manifest", type=Path, default=REPO / "eval" / "freeze-manifest.json")
    parser.add_argument("--fewshot-ids", type=Path, action="append", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.out.exists() and any(args.out.iterdir()):
            raise ValueError("use an empty output directory so an existing review is preserved")
        manifest = prepare(args.workbook, args.gold, args.freeze_manifest, args.fewshot_ids, args.out)
    except (KeyError, OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Prepared {len(manifest['record_ids'])} development cases in {args.out}. Review pending.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
