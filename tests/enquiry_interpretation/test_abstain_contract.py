"""v0.2.0 abstain rules, checked against whichever validator the seam is using."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from copilot.enquiry_interpretation import interpret, seam
from tests.support.helpers import ScriptedClient, completion, model_json


def _answered() -> dict:
    output = interpret(
        {"query": "What parameters does the API take?"},
        client=ScriptedClient([completion(model_json())]),
    )
    body = output.model_dump(mode="json")
    assert seam.validate_interpretation_output(body) == []
    return body


def test_success_serializes_a_present_null_abstain_reason() -> None:
    body = _answered()
    assert body["abstain"] is False
    assert "abstain_reason" in body
    assert body["abstain_reason"] is None
    encoded = json.dumps(body)
    assert '"abstain_reason": null' in encoded


def test_non_null_reason_is_const_and_forbidden_when_not_abstaining() -> None:
    body = _answered()
    body["abstain_reason"] = "model_unavailable"
    assert seam.validate_interpretation_output(body) == [
        "/abstain_reason: CONST: None was expected",
        "/abstain_reason: ABSTAIN_REASON_FORBIDDEN: abstain=false requires "
        'abstain_reason null; abstain_reason="model_unavailable"',
    ]


def test_missing_abstain_reason_key_is_required_when_not_abstaining() -> None:
    body = _answered()
    del body["abstain_reason"]
    assert seam.validate_interpretation_output(body) == [
        "/abstain_reason: REQUIRED: 'abstain_reason' is a required property",
        "/abstain_reason: ABSTAIN_REASON_FORBIDDEN: abstain=false requires "
        "abstain_reason null; abstain_reason=<absent>",
    ]


def test_whitespace_around_a_reason_is_rejected_and_not_trimmed() -> None:
    body = _answered()
    body["abstain"] = True
    body["abstain_reason"] = " model_unavailable "
    assert seam.validate_interpretation_output(body) == [
        "/abstain_reason: ENUM: ' model_unavailable ' is not one of "
        "['model_unavailable', 'invalid_after_repair', 'budget_exceeded', "
        "'no_rule_match', None]",
        "/abstain_reason: ENUM: ' model_unavailable ' is not one of "
        "['model_unavailable', 'invalid_after_repair', 'budget_exceeded', "
        "'no_rule_match']",
    ]
    exact = _answered()
    exact["abstain"] = True
    exact["abstain_reason"] = "model_unavailable"
    assert seam.validate_interpretation_output(exact) == []


def test_validation_module_identity() -> None:
    """Prove which copilot.validation.rules this process imported."""
    if os.environ.get("INTERPRET_VALIDATION") != "real":
        assert seam.validate_interpretation_output.__module__ == "tests.support.fake_contract"
        print("VALIDATION_RULES_FILE tests/support/fake_contract.py")
        return
    import copilot.validation.rules as rules

    root = Path(os.environ["INTERPRET_REAL_ROOT"]).resolve() if os.environ.get("INTERPRET_REAL_ROOT") else Path(__file__).resolve().parents[2]
    sha = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    print(f"VALIDATION_RULES_FILE {rules.__file__}")
    print(f"VALIDATION_HEAD {sha}")
    assert Path(rules.__file__).resolve().is_relative_to(root)
    assert sha == subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    assert seam._rules() is rules
