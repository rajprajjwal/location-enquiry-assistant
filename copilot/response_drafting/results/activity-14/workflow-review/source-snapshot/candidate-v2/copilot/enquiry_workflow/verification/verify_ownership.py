"""Replay saved ownership decisions without model requests or record writes."""
import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from copilot.enquiry_workflow import escalation, ownership_status
from copilot.models import InterpretationOutput
from copilot.safety import escalation_policy


def scores(rows):
    n = len(rows)
    tp = sum(row["actual"]["escalate"] and row["expected"]["escalate"] for row in rows)
    fp = sum(row["actual"]["escalate"] and not row["expected"]["escalate"] for row in rows)
    fn = sum(not row["actual"]["escalate"] and row["expected"]["escalate"] for row in rows)
    reasons = [row["actual"].get("reason") for row in rows if row["actual"]["escalate"]]
    correct = sum(row["actual"]["owner"] == row["expected"]["owner"] for row in rows)
    return {"cases": n, "owner_correct": correct, "owner_accuracy": correct / n,
            "escalation_true_positives": tp, "escalation_false_positives": fp, "escalation_false_negatives": fn,
            "escalation_precision": tp / (tp + fp) if tp + fp else None,
            "escalation_recall": tp / (tp + fn) if tp + fn else None,
            "escalation_reason_coverage": sum(bool(reason) for reason in reasons) / len(reasons) if reasons else None}


def verify(inputs, baseline_module, baseline_yaml, output, baseline_evidence=None):
    if output.exists():
        raise ValueError("Use a new output directory to retain previous results")
    rows = [json.loads(line) for line in inputs.read_text().splitlines()]
    if not rows or len(rows) != len({row["record_id"] for row in rows}):
        raise ValueError("Expected distinct saved case records")
    config = deepcopy(escalation_policy.policy())
    old_config = yaml.safe_load(baseline_yaml.read_text())
    spec = importlib.util.spec_from_file_location("saved_ownership_policy", baseline_module)
    old_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old_module)
    old_module.policy = lambda: old_config
    prior_status = old_module.customer_status
    if baseline_evidence is not None:
        evidence_spec = importlib.util.spec_from_file_location("saved_customer_evidence", baseline_evidence)
        evidence_module = importlib.util.module_from_spec(evidence_spec)
        evidence_spec.loader.exec_module(evidence_module)
        prior_status = lambda message: evidence_module.customer_status(
            message, old_config["customer_status"], actual_use=old_config.get("actual_use_detection", False))
    current_status = escalation_policy.customer_status
    current_triage = escalation.routine_support_assessment
    arms = {}
    for name, active_config, status in [("baseline", old_config, prior_status),
                                         ("candidate", config, current_status)]:
        predictions = []
        for row in rows:
            parsed = InterpretationOutput.model_validate(row["interpretation"])
            status_value, _ = ownership_status.review_customer_status(row["query"], row["history"], parsed)
            triage = (name == "candidate" and parsed.intent == "human_handoff"
                      and current_triage(row["query"], customer_status=status_value)
                      and not escalation.escalation.check(escalation.customer_question(row["query"]))["escalate"])
            if row["actual"]["escalate"] and not triage:
                actual = deepcopy(row["actual"])
            else:
                with patch.object(escalation_policy, "policy", return_value=active_config), \
                     patch.object(escalation_policy, "customer_status", side_effect=status), \
                     patch.object(ownership_status, "customer_status", side_effect=status), \
                     patch.object(escalation, "routine_support_assessment", side_effect=(
                         current_triage if name == "candidate" else lambda *args, **kwargs: False)), \
                     patch.object(escalation, "_model_category", return_value=SimpleNamespace(
                         category=None, reason=row["actual"]["reason"])):
                    route = escalation.route_enquiry(row["query"], parsed, history=row["history"])
                actual = {"owner": route["owner"], "escalate": route["should_escalate"],
                          "reason": route["reason"], "ownership_review": route["ownership_review"]}
            predictions.append({**row, "actual": actual})
        arms[name] = predictions
    summary = {"baseline": scores(arms["baseline"]), "candidate": scores(arms["candidate"]),
               "model_calls": 0, "record_writes": 0,
               "method": "Saved-interpretation replay; cached handoff classifications retained except rule-based first-line triage. Unchanged escalation metrics measure preservation.",
               "changes": [], "deferred": [], "escalations_preserved": True}
    for before, after in zip(arms["baseline"], arms["candidate"], strict=True):
        summary["escalations_preserved"] &= before["actual"]["escalate"] == after["actual"]["escalate"]
        if before["actual"]["owner"] != after["actual"]["owner"]:
            summary["changes"].append({"record_id": after["record_id"], "query": after["query"],
                "before": before["actual"]["owner"], "after": after["actual"]["owner"],
                "expected": after["expected"]["owner"],
                "improved": after["actual"]["owner"] == after["expected"]["owner"]})
        review = after["actual"].get("ownership_review", {})
        if review.get("status_deferred"):
            assert review.get("suggested_question") is None
            summary["deferred"].append(after["record_id"])
    output.mkdir(parents=True)
    for name, predictions in arms.items():
        (output / f"{name}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in predictions))
    (output / "scores.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--baseline-module", type=Path, required=True)
    parser.add_argument("--baseline-policy", type=Path, required=True)
    parser.add_argument("--baseline-evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.inputs, args.baseline_module, args.baseline_policy, args.output, args.baseline_evidence)
