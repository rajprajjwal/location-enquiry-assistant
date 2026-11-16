"""Acceptance test 4: missing_required_fields is computed from values only."""

from __future__ import annotations

from copilot.interpret.postcheck import postcheck
from tests.support.helpers import model_json


def test_model_supplied_missing_list_is_ignored() -> None:
    payload = model_json(
        qualification={"region": {"value": "India", "evidence": "in India"}},
    )
    import json

    body = json.loads(payload)
    body["missing_required_fields"] = ["region"]
    body["qualification"]["missing_required_fields"] = ["region"]
    result = postcheck(json.dumps(body), query="We operate in India.")
    assert result["errors"] == []
    missing = result["output"]["missing_required_fields"]
    assert "region" not in missing
    assert missing == result["output"]["qualification_details"]["missing_required_fields"]
    assert "timeline" in missing
    assert "current_provider" in missing


def test_history_value_is_not_missing() -> None:
    result = postcheck(
        model_json(api="directions", intent="pricing_quote", sub_intent="pricing_quote", team="Sales"),
        query="What is the directions price?",
        history=[
            {"role": "user", "text": "We operate in India."},
            {"role": "assistant", "text": "Before I answer, one question?"},
        ],
    )
    qual = result["output"]["qualification_details"]
    assert result["errors"] == []
    assert qual["region"] == "India"
    assert "region" not in qual["missing_required_fields"]
    assert result["output"]["field_provenance"]["region"] == "history"
    assert qual["timeline"] is None


def test_known_fact_is_not_missing() -> None:
    result = postcheck(
        model_json(),
        query="What parameters does the API take?",
        known_facts=[{"field": "timeline", "value": "by Q3 2026", "source": "state_store"}],
    )
    qual = result["output"]["qualification_details"]
    assert result["errors"] == []
    assert qual["timeline"] == "by Q3 2026"
    assert "timeline" not in qual["missing_required_fields"]
    assert result["output"]["field_provenance"]["timeline"] == "state"


def test_leave_that_open_stays_missing() -> None:
    result = postcheck(
        model_json(
            qualification={"timeline": {"value": "leave that open", "evidence": "leave that open"}},
        ),
        query="leave that open",
    )
    qual = result["output"]["qualification_details"]
    assert qual["timeline"] is None
    assert "timeline" in qual["missing_required_fields"]


def test_later_decline_overrides_history() -> None:
    result = postcheck(
        model_json(api="directions", intent="pricing_quote", sub_intent="pricing_quote", team="Sales"),
        query="leave timeline open",
        history=[{"role": "user", "text": "We can go live by Q3 2026."}],
    )
    qual = result["output"]["qualification_details"]
    assert result["errors"] == []
    assert qual["timeline"] is None
    assert "timeline" in qual["missing_required_fields"]


def test_assistant_scoped_decline_clears_only_that_field() -> None:
    result = postcheck(
        model_json(api="directions", intent="pricing_quote", sub_intent="pricing_quote", team="Sales"),
        query="leave that open",
        history=[
            {"role": "user", "text": "We operate in India and can go live by Q3 2026."},
            {"role": "assistant", "text": "What timeline should I use?"},
        ],
    )
    qual = result["output"]["qualification_details"]
    assert qual["region"] == "India"
    assert qual["timeline"] is None
    assert "timeline" in qual["missing_required_fields"]
    assert "region" not in qual["missing_required_fields"]
