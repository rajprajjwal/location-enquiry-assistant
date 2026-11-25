"""Export a fixed working trace sample without selecting on model performance."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from openpyxl import load_workbook

from copilot.enquiry_interpretation.gt_adapter import from_gt_question
from copilot.paths import REPO_ROOT
from copilot.validation.rules import normalize_enum


def prepare(output):
    source = REPO_ROOT / "data/ground-truth.xlsx"
    allowlist = REPO_ROOT / "copilot/response_drafting/results/activity-14/workflow-review/original-working-reference.json"
    membership = {r["record_id"]: r for r in json.loads(allowlist.read_text())["cases"]}
    if len(membership) != 317:
        raise ValueError("Expected the established 317-case working allowlist")
    frozen = set(json.loads((REPO_ROOT / "eval/frozen-interpretation/manifest.json").read_text())["frozen_record_ids"])
    if frozen & membership.keys():
        raise ValueError("Working allowlist contains frozen IDs")
    workbook = load_workbook(source, read_only=True, data_only=True)
    try:
        rows = workbook["Data"].iter_rows(values_only=True)
        headers = next(rows)
        records = {}
        for values in rows:
            row = dict(zip(headers, values))
            identifier = row["id"]
            if identifier not in membership:
                continue
            if row["split"] != "eval" or row["frozen_core"] is True:
                raise ValueError("Allowlisted record is no longer non-frozen eval")
            query, history = from_gt_question(row["question"])
            records[identifier] = {
                "record_id": identifier, "input": {"query": query, "history": history, "known_facts": []},
                "bucket": row["bucket"], "api": normalize_enum("api", row["api"]),
                "team": row["primary_team"], "split": "working_eval", "frozen_core": False,
                "group": membership[identifier]["group"], "fold": membership[identifier]["fold"],
            }
    finally:
        workbook.close()
    if records.keys() != membership.keys():
        raise ValueError("Current workbook does not contain every allowlisted working record")
    selected, groups = [], set()
    counts = Counter()
    for bucket in sorted({r["bucket"] for r in records.values()}):
        options = [r for r in records.values() if r["bucket"] == bucket and r["group"] not in groups]
        row = min(options, key=lambda r: (counts[r["api"]], r["record_id"]))
        selected.append(row)
        counts[row["api"]] += 1
        groups.add(row["group"])
    if len(counts) != 4:
        raise ValueError("Working trace sample must cover all four APIs")
    output.mkdir(parents=True, exist_ok=False)
    blob = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected).encode()
    (output / "inputs.jsonl").write_bytes(blob)
    manifest = {"selection": "One case per bucket, preferring the least-represented API, then sorted ID; one per established group.",
                "working_pool_size": len(records), "selected": len(selected),
                "workbook_sha256": sha256(source.read_bytes()).hexdigest(),
                "allowlist_sha256": sha256(allowlist.read_bytes()).hexdigest(),
                "inputs_sha256": sha256(blob).hexdigest(), "frozen_or_holdout_selected": 0,
                "buckets": dict(Counter(row["bucket"] for row in selected)),
                "apis": dict(Counter(row["api"] for row in selected)),
                "record_ids": [row["record_id"] for row in selected]}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    prepare(parser.parse_args().out)
