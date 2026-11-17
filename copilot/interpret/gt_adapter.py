"""Export manifest-selected Activity 2 questions as interpretation input JSONL."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from copilot.models import InterpretationInput


DEFAULT_MANIFEST = Path(__file__).resolve().parents[2] / "eval" / "freeze-manifest.json"
TURN_MARKER = re.compile(r"^\s*\[(user|assistant)\]\s*", re.IGNORECASE)


def from_gt_question(question: str) -> tuple[str, list[dict[str, str]]]:
    """Take the last user turn as the query, preserving the prior turns in order."""
    turns: list[tuple[str, list[str]]] = []
    for line in question.strip().splitlines():
        marker = TURN_MARKER.match(line)
        if marker:
            turns.append((marker.group(1).lower(), [line[marker.end():]]))
        else:
            if not turns:
                turns.append(("user", []))
            turns[-1][1].append(line)

    messages = [{"role": role, "text": "\n".join(lines).strip()} for role, lines in turns]
    if not messages or any(not message["text"] for message in messages):
        raise ValueError("question contains an empty turn")
    for index in range(len(messages) - 1, -1, -1):
        if messages[index]["role"] == "user":
            return messages[index]["text"], messages[:index]
    raise ValueError("question contains no user turn")


def load_core_inputs(workbook_path: Path, manifest_path: Path) -> list[InterpretationInput]:
    """Validate the workbook hash and export only the core IDs in manifest order."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ids = manifest["frozen_record_ids"]
    if not isinstance(ids, list) or not ids or any(
        not isinstance(record_id, str) or not record_id.strip() for record_id in ids
    ):
        raise ValueError("manifest frozen_record_ids must be a nonempty list of record IDs")
    selected = set(ids)
    if len(selected) != len(ids) or len(ids) != manifest["frozen_file"]["records"]:
        raise ValueError("manifest core IDs contain duplicates or disagree with the recorded count")

    source = manifest["sources"]["gt_v2_5.xlsx"]
    inputs: dict[str, InterpretationInput] = {}
    with workbook_path.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != source["sha256"]:
            raise ValueError("workbook SHA-256 does not match the freeze manifest")
        handle.seek(0)
        workbook = load_workbook(handle, read_only=True, data_only=True)
        try:
            rows = workbook[source["sheet"]].values
            headers = next(rows, ())
            columns = ("id", "question", "split", "frozen_core")
            if any(headers.count(column) != 1 for column in columns):
                raise ValueError("ground-truth sheet must have one id, question, split and frozen_core column")
            id_col, question_col, split_col, core_col = (headers.index(column) for column in columns)
            for row in rows:
                record_id = row[id_col]
                if record_id not in selected:
                    continue
                if record_id in inputs:
                    raise ValueError(f"duplicate workbook record ID: {record_id}")
                if row[split_col] != "eval" or row[core_col] is not True:
                    raise ValueError(f"{record_id} is not marked as a frozen eval record")
                question = row[question_col]
                if not isinstance(question, str):
                    raise ValueError(f"{record_id}: question must be text")
                try:
                    query, history = from_gt_question(question)
                    inputs[record_id] = InterpretationInput(
                        record_id=record_id, query=query, history=history, known_facts=[]
                    )
                except ValueError as exc:
                    raise ValueError(f"{record_id}: {exc}") from exc
        finally:
            workbook.close()

    missing = selected - inputs.keys()
    if missing:
        raise ValueError(f"manifest records missing from workbook: {', '.join(sorted(missing))}")
    return [inputs[record_id] for record_id in ids]


def write_inputs(path: Path, inputs: list[InterpretationInput]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as output:
        temp_path = Path(output.name)
        try:
            for item in inputs:
                output.write(item.model_dump_json() + "\n")
            output.close()
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", required=True, type=Path, help="local GT workbook")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, type=Path)
    parser.add_argument("--out", required=True, type=Path, help="destination for inputs.jsonl")
    args = parser.parse_args(argv)

    try:
        if args.out.resolve() in {args.workbook.resolve(), args.manifest.resolve()}:
            raise ValueError("output path must differ from the workbook and manifest paths")
        inputs = load_core_inputs(args.workbook, args.manifest)
        write_inputs(args.out, inputs)
    except (InvalidFileException, KeyError, OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    multi_turn = sum(bool(item.history) for item in inputs)
    print(f"Exported {len(inputs)} frozen eval inputs ({multi_turn} with history) to {args.out}. "
          "Holdout cases selected: 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
