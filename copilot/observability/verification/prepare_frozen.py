"""Bind tracing inputs to the unchanged, pinned 80-case frozen export."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from copilot.paths import REPO_ROOT


def canonical_rows():
    source = REPO_ROOT / "eval/frozen-interpretation"
    manifest = json.loads((source / "manifest.json").read_text())
    inputs = source / "inputs.jsonl"
    gold = source / "gold.jsonl"
    if sha256(inputs.read_bytes()).hexdigest() != manifest["inputs_sha256"]:
        raise ValueError("Pinned frozen inputs changed")
    if sha256(gold.read_bytes()).hexdigest() != manifest["frozen_file"]["sha256"]:
        raise ValueError("Pinned frozen metadata changed")
    labels = {r["record_id"]: r for r in map(json.loads, gold.read_text().splitlines())}
    rows = []
    for context in map(json.loads, inputs.read_text().splitlines()):
        identifier = context["record_id"]
        label = labels[identifier]
        if not label["frozen_core"] or label["split"] != "eval":
            raise ValueError("Frozen input is not an approved eval record")
        rows.append({"record_id": identifier, "input": {k: context[k] for k in ("query", "history", "known_facts")},
                     **{k: label[k] for k in ("bucket", "api", "team")}, "split": "frozen", "frozen_core": True})
    if len(rows) != 80 or {r["record_id"] for r in rows} != set(manifest["frozen_record_ids"]):
        raise ValueError("Expected exactly the pinned 80 frozen cases")
    return rows


def validate(rows):
    if sorted(rows, key=lambda r: r["record_id"]) != sorted(canonical_rows(), key=lambda r: r["record_id"]):
        raise ValueError("Frozen trace inputs must match the pinned 80 cases exactly")


def prepare(output):
    rows = canonical_rows()
    output.mkdir(parents=True, exist_ok=False)
    blob = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode()
    (output / "inputs.jsonl").write_bytes(blob)
    source = REPO_ROOT / "eval/frozen-interpretation"
    manifest = {"records": len(rows), "inputs_sha256": sha256(blob).hexdigest(),
                "source_hashes": {name: sha256((source / name).read_bytes()).hexdigest()
                                  for name in ("inputs.jsonl", "gold.jsonl", "manifest.json")},
                "apis": dict(Counter(r["api"] for r in rows)), "holdout_selected": 0,
                "labels_usage": "Bucket, API and team are trace metadata only; no expected answer is passed to the workflow."}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    prepare(parser.parse_args().out)
