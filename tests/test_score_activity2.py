from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from copilot.validation.rules import compute_missing_required_fields
from eval.score_activity2 import SLOTS, compare_slot, main, score_activity2


def qualification(api: str | None, **values) -> dict:
    qual = dict.fromkeys(SLOTS)
    if api:
        qual["use_case_api"] = {"api": api, "use_case": None}
    qual.update(values)
    missing = compute_missing_required_fields(qual)
    return {**qual, "missing_required_fields": missing, "complete": not missing}


def gold(record_id: str, qual: dict) -> dict:
    return {
        "record_id": record_id, "intent": "pricing_quote", "api": "directions", "team": "Sales",
        "bucket": "qualification", "split": "eval", "frozen_core": True,
        "outputs": {"qualification_details": qual},
    }


def prediction(record_id: str, qual: dict, *, intent="pricing_quote", team="Sales", repair=0) -> dict:
    api = (qual["use_case_api"] or {}).get("api")
    return {
        "record_id": record_id, "intent": intent, "sub_intent": None, "api": api, "team": team,
        "qualification_details": qual, "missing_required_fields": qual["missing_required_fields"],
        "field_provenance": {}, "confidence": dict.fromkeys(("intent", "api", "team")),
        "abstain": api is None, "abstain_reason": "model_unavailable" if api is None else None,
        "trace": {
            "model": "fixture", "prompt_version": "fixture", "approx_input_tokens": 0,
            "approx_output_tokens": 0, "latency_ms": 0, "repair_attempts": repair,
            "model_calls": 1 + repair, "rule_model_disagreements": [],
        },
    }


def write_rows(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class TestActivity2Scorer(TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.predictions_path = self.root / "predictions.jsonl"
        self.gold_path = self.root / "gold.jsonl"
        self.manifest_path = self.root / "manifest.json"

    def set_gold(self, rows: list[dict]) -> None:
        write_rows(self.gold_path, rows)
        manifest = {
            "manifest_version": 3, "frozen_record_ids": [row["record_id"] for row in rows],
            "frozen_file": {"records": len(rows), "sha256": hashlib.sha256(self.gold_path.read_bytes()).hexdigest()},
        }
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def score(self):
        return score_activity2(self.predictions_path, self.gold_path, self.manifest_path, "fixture-commit")

    def test_metrics_on_six_cases_with_hand_calculated_results(self) -> None:
        api = "directions"
        volume = {"raw": "1 lakh", "requests_per_month": None}
        provider = "Google Maps Platform"
        complete = qualification(api, region="India", monthly_volume=volume, current_provider=provider, timeline="Q3 2027")
        api_only = qualification(api)
        api_region = qualification(api, region="India")
        self.set_gold([
            gold("A", complete), gold("B", qualification(api, monthly_volume=volume)),
            gold("C", api_region), gold("D", api_region), gold("E", api_only), gold("F", api_only),
        ])
        complete_pred = qualification(
            api, region="PAN-INDIA", monthly_volume={"raw": "100,000", "requests_per_month": 100_000},
            current_provider=provider, timeline="start in Q3 2027",
        )
        wrong_api_volume = qualification(
            "autocomplete", monthly_volume={"raw": "200k", "requests_per_month": 200_000}, budget="10k",
        )
        write_rows(self.predictions_path, [
            prediction("F", api_only),
            prediction("E", qualification(api, current_provider=provider), intent="pricing_comparison"),
            {**prediction("D", api_region), "unexpected": True},
            prediction("C", qualification(None), intent=None, team=None),
            prediction("B", wrong_api_volume, team="Support"),
            prediction("A", complete_pred, repair=1),
        ])

        scores, rows = self.score()
        self.assertEqual([row["record_id"] for row in rows], list("ABCDEF"))
        for field in ("intent_acc", "api_acc", "team_acc"):
            self.assertEqual(scores[field], 3 / 6)
        self.assertEqual(scores["qual_f1"], 14 / 24)  # 7 TP, 4 FP, 6 FN
        self.assertEqual(scores["qual_f1_excl_api"], 8 / 14)  # 4 TP, 3 FP, 3 FN
        self.assertEqual(scores["missing_recall"], 13 / 17)
        self.assertEqual(scores["missing_precision"], 13 / 15)
        self.assertEqual(scores["schema_valid_rate"], 5 / 6)
        self.assertEqual(scores["abstain_rate"], 1 / 6)
        self.assertEqual(scores["repair_rate"], 1 / 6)
        self.assertEqual(scores["model_calls"], 6)
        self.assertEqual(scores["breakdowns"]["api"][api]["records"], 6)
        self.assertFalse(scores["passed"])
        self.assertTrue(rows[3]["validation_errors"])

    def test_normalizes_units_aliases_and_null_like_fields(self) -> None:
        for raw, equivalent in (("1 crore", "10M"), ("2.5 lakh", "250 thousand"), ("50k", "50,000")):
            with self.subTest(raw=raw):
                actual = compare_slot("monthly_volume", {"raw": raw}, {"raw": equivalent})
                self.assertEqual((actual["tp"], actual["fp"], actual["fn"]), (1, 0, 0))
        self.assertEqual(compare_slot("monthly_volume", {"raw": "variable"}, {"raw": "VARIABLE"})["tp"], 1)
        self.assertEqual(compare_slot("current_provider", "MapmyIndia", "Mappls (MapmyIndia)")["tp"], 1)
        self.assertEqual(compare_slot("region", " ＩＮＤＩＡ. ", "pan-India")["tp"], 1)
        self.assertEqual(compare_slot("budget", None, " N/A ")["fp"], 0)
        self.assertEqual(compare_slot("timeline", "Q3", "Q3 2027")["tp"], 0)
        self.assertEqual(compare_slot("timeline", "July", "start in July")["tp"], 1)

    def test_rejects_wrong_gold_hash_and_missing_extra_or_duplicate_predictions(self) -> None:
        qual = qualification("directions")
        a = prediction("A", qual)
        b = prediction("B", qual)
        self.set_gold([gold("A", qual)])
        for rows, error in (([], "missing="), ([a, b], "extra="), ([a, a], "duplicate record_id")):
            with self.subTest(error=error):
                write_rows(self.predictions_path, rows)
                with self.assertRaisesRegex(ValueError, error):
                    self.score()
        with self.gold_path.open("ab") as gold_file:
            gold_file.write(b"\n")
        with self.assertRaisesRegex(ValueError, "gold SHA-256"):
            self.score()

    def test_writes_identical_reports_on_rerun(self) -> None:
        qual = qualification("directions")
        self.set_gold([gold("A", qual)])
        write_rows(self.predictions_path, [prediction("A", qual)])
        common = [
            "--predictions", str(self.predictions_path), "--gold", str(self.gold_path),
            "--manifest", str(self.manifest_path), "--git-commit", "fixture-commit",
        ]
        first, second = self.root / "first", self.root / "second"
        self.assertEqual(main([*common, "--out", str(first)]), 0)
        self.assertEqual(main([*common, "--out", str(second)]), 0)
        for name in ("scores.json", "per_record.jsonl", "report.md"):
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
        self.assertTrue(json.loads((first / "scores.json").read_text())["passed"])

    def test_development_requires_review_and_does_not_return_frozen_acceptance(self) -> None:
        qual = qualification("directions")
        expected = {**gold("A", qual), "frozen_core": False, "review_priority": "high",
                    "template_family": "dev-family", "verification_status": "verified_live"}
        write_rows(self.gold_path, [expected])
        write_rows(self.predictions_path, [prediction("A", qual)])
        gold_hash = hashlib.sha256(self.gold_path.read_bytes()).hexdigest()
        manifest = {
            "manifest_version": 1, "mode": "development", "record_ids": ["A"],
            "gold_file": {"records": 1, "sha256": gold_hash},
            "excluded_record_ids": ["F"], "excluded_template_families": ["frozen-family"],
        }
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "scoring mode does not match"):
            self.score()
        reviews = self.root / "reviews.csv"
        review = {
            "record_id": "A", "review_status": "approved", "reviewer": "fixture reviewer",
            "review_date": "2026-11-17", "second_review_date": "", "second_review_evidence": "",
            "gold_sha256": gold_hash,
        }

        def score_dev():
            with reviews.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(review))
                writer.writeheader()
                writer.writerow(review)
            return score_activity2(self.predictions_path, self.gold_path, self.manifest_path,
                                   "fixture-commit", mode="development", reviews_path=reviews)

        with self.assertRaisesRegex(ValueError, "review incomplete: 0/1"):
            score_dev()
        provisional, _ = score_activity2(
            self.predictions_path, self.gold_path, self.manifest_path, "fixture-commit",
            mode="development", allow_unreviewed=True,
        )
        self.assertTrue(provisional["provisional"])
        self.assertEqual(provisional["human_gold_review"], "skipped")
        self.assertEqual(provisional["intent_acc"], 1.0)
        self.assertIsNone(provisional["passed"])
        review.update(second_review_date="2026-11-17", second_review_evidence="fixture second pass")
        scores, _ = score_dev()
        self.assertEqual(scores["evaluation_mode"], "development")
        self.assertFalse(scores["provisional"])
        self.assertEqual(scores["human_gold_review"], "complete")
        self.assertEqual(scores["intent_acc"], 1.0)
        self.assertIsNone(scores["passed"])

        manifest["excluded_template_families"].append("dev-family")
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "excluded template families"):
            score_dev()
        with self.assertRaisesRegex(ValueError, "excluded template families"):
            score_activity2(self.predictions_path, self.gold_path, self.manifest_path, "fixture-commit",
                            mode="development", allow_unreviewed=True)

    def test_frozen_mode_rejects_review_override(self) -> None:
        qual = qualification("directions")
        self.set_gold([gold("A", qual)])
        write_rows(self.predictions_path, [prediction("A", qual)])
        with self.assertRaisesRegex(ValueError, "only available in development"):
            score_activity2(self.predictions_path, self.gold_path, self.manifest_path, "fixture-commit",
                            allow_unreviewed=True)
