"""interpret() on synthetic inputs with a mocked model, including history."""

from __future__ import annotations

from copilot.enquiry_interpretation import interpret
from copilot.enquiry_interpretation import seam
from tests.support.helpers import ScriptedClient, completion, model_json


def _valid(output) -> None:
    assert seam.validate_interpretation_output(output.model_dump(mode="json")) == []


def test_rules_fill_qualification_when_the_model_agrees() -> None:
    query = (
        "We are a delivery company in India. We currently use Google Maps. "
        "We need 20,000 directions requests a month and go-live by Q3 2026."
    )
    reply = model_json(
        intent="pricing_quote",
        sub_intent="pricing_quote",
        api="directions",
        team="Sales",
        qualification={
            "region": {"value": "India", "evidence": "in India"},
            "current_provider": {"value": "Google Maps", "evidence": "Google Maps"},
            "monthly_volume": {
                "value": "20,000 directions requests a month",
                "evidence": "20,000 directions requests a month",
            },
            "timeline": {"value": "by Q3 2026", "evidence": "by Q3 2026"},
        },
    )
    output = interpret({"query": query}, client=ScriptedClient([completion(reply)]))
    body = output.model_dump(mode="json")
    qual = body["qualification_details"]
    assert body["abstain"] is False
    assert body["intent"] == "pricing_quote"
    assert body["api"] == "directions"
    assert body["team"] == "Sales"
    assert qual["region"] == "India"
    assert qual["current_provider"] == "Google Maps Platform"
    assert qual["monthly_volume"]["requests_per_month"] == 20000
    assert qual["timeline"] == "by Q3 2026"
    assert qual["missing_required_fields"] == []
    assert qual["complete"] is True
    assert body["trace"]["model_calls"] == 1
    _valid(output)


def test_history_region_survives_and_assistant_text_does_not_set_a_timeline() -> None:
    reply = model_json(
        intent="pricing_quote",
        sub_intent="pricing_quote",
        api="directions",
        team="Sales",
    )
    output = interpret(
        {
            "query": "What is the directions price?",
            "history": [
                {"role": "user", "text": "We operate in India."},
                {"role": "assistant", "text": "Before I answer, one question?"},
            ],
        },
        client=ScriptedClient([completion(reply)]),
    )
    body = output.model_dump(mode="json")
    qual = body["qualification_details"]
    assert qual["region"] == "India"
    assert body["field_provenance"]["region"] == "history"
    assert "region" not in qual["missing_required_fields"]
    assert qual["timeline"] is None
    assert "timeline" in qual["missing_required_fields"]
    assert body["api"] == "directions"
    _valid(output)


def test_known_fact_and_a_repair_are_both_applied() -> None:
    bad = model_json(intent="nope", api="directions")
    good = model_json(
        intent="docs_how_to",
        sub_intent="parameter_question",
        api="directions",
        team="Support",
    )
    client = ScriptedClient([completion(bad), completion(good, latency_ms=4)])
    output = interpret(
        {
            "query": "What parameters does the API take?",
            "known_facts": [
                {"field": "region", "value": "India", "source": "state_store"}
            ],
        },
        client=client,
    )
    body = output.model_dump(mode="json")
    assert body["intent"] == "docs_how_to"
    assert body["abstain"] is False
    assert body["qualification_details"]["region"] == "India"
    assert body["field_provenance"]["region"] == "state"
    assert body["trace"]["model_calls"] == 2
    assert body["trace"]["repair_attempts"] == 1
    assert body["trace"]["latency_ms"] == 11
    assert "<<" not in client.calls[0]["messages"][-1]["content"]
    assert "What parameters does the API take?" in client.calls[0]["messages"][-1]["content"]
    _valid(output)
