"""Acceptance test 3: post-check normalisation, grounding, and parsing."""

from __future__ import annotations

import logging

from copilot.interpret.postcheck import postcheck
from tests.support.helpers import model_json, model_payload


def test_out_of_vocab_intent_api_and_team_are_invalid() -> None:
    result = postcheck(
        model_json(intent="smalltalk", api="Maps", team="Finance"),
        query="hello there",
    )
    assert result["errors"]
    assert result["output"]["intent"] == "smalltalk"
    assert result["output"]["api"] == "Maps"
    assert result["output"]["team"] == "Finance"
    codes = " ".join(result["errors"])
    assert "/intent" in codes and "ENUM" in codes
    assert "/api" in codes
    assert "/team" in codes


def test_case_variant_api_is_normalised() -> None:
    result = postcheck(
        model_json(api="Directions"),
        query="What parameters does the API take?",
    )
    assert result["errors"] == []
    assert result["output"]["api"] == "directions"
    assert result["output"]["qualification_details"]["use_case_api"]["api"] == "directions"


def test_provider_alias_is_canonicalised() -> None:
    result = postcheck(
        model_json(
            api="autocomplete",
            qualification={
                "current_provider": {"value": "MapmyIndia", "evidence": "MapmyIndia"}
            },
        ),
        query="Is MapmyIndia supported?",
    )
    assert result["errors"] == []
    assert result["output"]["qualification_details"]["current_provider"] == "Mappls (MapmyIndia)"


def test_sub_intent_outside_parent_is_nulled_and_logged(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="copilot.interpret"):
        result = postcheck(
            model_json(
                intent="pricing_quote",
                sub_intent="billing_dispute",
                api="distance_matrix",
                team="Sales",
            ),
            query="hello",
        )
    assert result["errors"] == []
    assert result["output"]["sub_intent"] is None
    assert result["output"]["intent"] == "pricing_quote"
    assert any("billing_dispute" in rec.message and "null" in rec.message for rec in caplog.records)


def test_ungrounded_value_is_dropped() -> None:
    result = postcheck(
        model_json(
            api="reverse_geocode",
            qualification={"region": {"value": "Atlantis", "evidence": "Atlantis"}},
        ),
        query="hello there",
    )
    assert result["errors"] == []
    assert result["output"]["qualification_details"]["region"] is None
    assert "region" in result["output"]["missing_required_fields"]


def test_think_block_is_stripped_before_the_json_object() -> None:
    decoy = model_json(intent="human_handoff", sub_intent="security_incident", api="autocomplete")
    real = model_json()
    result = postcheck(f"<think>{decoy}</think>\n{real}", query="What parameters does the API take?")
    assert result["errors"] == []
    assert result["output"]["intent"] == "docs_how_to"
    assert result["output"]["api"] == "directions"


def test_trailing_prose_keeps_the_first_json_object() -> None:
    result = postcheck(
        model_json() + "\nHope this helps!",
        query="What parameters does the API take?",
    )
    assert result["errors"] == []
    assert result["output"]["intent"] == "docs_how_to"


def test_rule_api_wins_over_a_different_model_api() -> None:
    result = postcheck(
        model_json(api="autocomplete"),
        query="We need directions for the fleet.",
    )
    assert result["errors"] == []
    assert result["output"]["api"] == "directions"
    assert "api" in result["output"]["trace"]["rule_model_disagreements"]
    assert result["output"]["field_provenance"]["use_case_api"] == "rule"
