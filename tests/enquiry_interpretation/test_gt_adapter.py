from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from openpyxl import Workbook

from copilot.enquiry_interpretation.gt_adapter import from_gt_question, load_core_inputs, write_inputs


class TestGroundTruthAdapter(TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.workbook_path = self.root / "gt.xlsx"
        self.manifest_path = self.root / "manifest.json"

    def write_fixture(self, rows: list[tuple], ids: list[str]) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Data"
        sheet.append(["id", "question", "split", "frozen_core", "context", "reference_answer"])
        for row in rows:
            sheet.append([*row, "gold evidence", "gold answer"])
        workbook.save(self.workbook_path)
        manifest = {
            "frozen_record_ids": ids,
            "frozen_file": {"records": len(ids)},
            "sources": {"gt_v2_5.xlsx": {
                "sheet": "Data",
                "sha256": hashlib.sha256(self.workbook_path.read_bytes()).hexdigest(),
            }},
        }
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def test_exports_manifest_order_and_keeps_only_interpreter_fields(self) -> None:
        question = "[user] We need Directions.\nIn India.\n[assistant] What volume?\n[user] 20,000 per month."
        self.write_fixture([
            ("core-a", question, "eval", True),
            ("holdout-a", "Holdout question", "holdout", False),
            ("core-b", "How does Autocomplete work?", "eval", True),
        ], ["core-b", "core-a"])
        path = self.root / "run" / "inputs.jsonl"
        write_inputs(path, load_core_inputs(self.workbook_path, self.manifest_path))
        result = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(result, [
            {"record_id": "core-b", "query": "How does Autocomplete work?", "history": [], "known_facts": []},
            {"record_id": "core-a", "query": "20,000 per month.", "known_facts": [], "history": [
                {"role": "user", "text": "We need Directions.\nIn India."},
                {"role": "assistant", "text": "What volume?"},
            ]},
        ])

    def test_rejects_inconsistent_manifest_and_workbook(self) -> None:
        row = ("core-a", "Question", "eval", True)
        checks = [
            ([row], ["core-a", "core-a"], "duplicates"),
            ([row, row], ["core-a"], "duplicate workbook record"),
            ([row], ["core-b"], "missing from workbook"),
            ([("core-a", "Question", "holdout", True)], ["core-a"], "not marked as a frozen eval"),
        ]
        for rows, ids, error in checks:
            with self.subTest(rows=rows, ids=ids):
                self.write_fixture(rows, ids)
                with self.assertRaisesRegex(ValueError, error):
                    load_core_inputs(self.workbook_path, self.manifest_path)

    def test_rejects_workbook_with_wrong_hash(self) -> None:
        self.write_fixture([("core-a", "Question", "eval", True)], ["core-a"])
        with self.workbook_path.open("ab") as file:
            file.write(b"changed")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            load_core_inputs(self.workbook_path, self.manifest_path)

    def test_excludes_assistant_reply_after_final_question(self) -> None:
        self.assertEqual(from_gt_question("[user] Question\n[assistant] Expected reply"), ("Question", []))
        with self.assertRaisesRegex(ValueError, "no user turn"):
            from_gt_question("[assistant] Reply only")
