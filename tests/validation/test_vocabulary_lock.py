"""Lock vocabulary tables the interpretation rules read.

Purpose: fail if enums, required fields, or provider aliases drift.
Use case: a schema or alias edit must update the other side in the same change.
Example: ``MapmyIndia`` stays an alias of ``Mappls (MapmyIndia)``.
"""

from __future__ import annotations

import json
from importlib.metadata import version
from pathlib import Path

from jsonschema import Draft202012Validator

from copilot.validation.rules import REQUIRED_FIELDS, load_vocab
from mapping.map_gt import PROVIDER_ALIASES, _PROVIDER_ALIAS_EXTRA

REPO = Path(__file__).resolve().parents[2]


def _load(path: str) -> dict:
    return json.loads((REPO / path).read_text(encoding="utf-8"))


def test_jsonschema_pin_matches_repair_messages() -> None:
    assert version("jsonschema") == "4.26.0"


def test_required_fields_follow_vocab_order() -> None:
    vocab = _load("vocab/controlled-vocabulary.json")
    assert REQUIRED_FIELDS == tuple(vocab["qualification_required_fields"])
    assert REQUIRED_FIELDS == (
        "use_case_api",
        "region",
        "monthly_volume",
        "current_provider",
        "timeline",
    )


def test_provider_aliases_match_the_mapper() -> None:
    expected = {**PROVIDER_ALIASES, **_PROVIDER_ALIAS_EXTRA}
    assert dict(load_vocab().provider_aliases) == expected
    providers = set(load_vocab().providers)
    assert set(expected.values()) <= providers


def test_loaded_vocab_matches_the_file() -> None:
    raw = _load("vocab/controlled-vocabulary.json")
    vocab = load_vocab()
    assert vocab.intents == tuple(raw["intents"])
    assert vocab.sub_intents == tuple(raw["sub_intents"])
    assert vocab.apis == tuple(raw["apis"])
    assert vocab.teams == tuple(raw["teams"])
    assert vocab.providers == tuple(raw["providers"])
    assert {
        key: tuple(value) for key, value in vocab.intent_to_sub_intents.items()
    } == {key: tuple(value) for key, value in raw["intent_to_sub_intents"].items()}


def test_interpretation_output_enums_match_vocab() -> None:
    raw = _load("vocab/controlled-vocabulary.json")
    schema = _load("contracts/interpretation/interpretation_output.schema.json")
    props = schema["properties"]
    assert schema["x-spec-version"] == "0.2.0"
    assert props["intent"]["enum"][:-1] == raw["intents"]
    assert props["intent"]["enum"][-1] is None
    assert props["api"]["enum"][:-1] == raw["apis"]
    assert props["api"]["enum"][-1] is None
    assert props["team"]["enum"][:-1] == raw["teams"]
    assert props["team"]["enum"][-1] is None
    assert "unknown" not in props["intent"]["enum"]
    assert "unknown" not in props["api"]["enum"]
    assert "unknown" not in props["team"]["enum"]
    closed = schema["allOf"][0]["then"]["properties"]
    assert closed["intent"]["enum"] == raw["intents"]
    assert closed["api"]["enum"] == raw["apis"]
    assert closed["team"]["enum"] == raw["teams"]
    reasons = props["abstain_reason"]["enum"]
    assert reasons[-1] is None
    assert "no_rule_match" in reasons[:-1]
    assert props["sub_intent"]["enum"][:-1] == raw["sub_intents"]
    assert props["sub_intent"]["enum"][-1] is None
    assert props["missing_required_fields"]["items"]["enum"] == raw[
        "qualification_required_fields"
    ]
    qual = _load("schemas/qualification_details.schema.json")
    assert qual["properties"]["use_case_api"]["properties"]["api"]["enum"] == raw["apis"]
    provider_enum = qual["properties"]["current_provider"]["enum"]
    assert provider_enum[:-1] == raw["providers"]
    assert provider_enum[-1] is None


def test_known_fact_fields_match_qualification_properties() -> None:
    raw = _load("vocab/controlled-vocabulary.json")
    schema = _load("contracts/interpretation/known_fact.schema.json")
    assert schema["properties"]["field"]["enum"] == (
        raw["qualification_required_fields"] + raw["qualification_optional_fields"]
    )


def test_contract_schemas_are_draft_2020_12() -> None:
    paths = [
        "contracts/interpretation/turn.schema.json",
        "contracts/interpretation/known_fact.schema.json",
        "contracts/interpretation/interpretation_input.schema.json",
        "contracts/interpretation/interpretation_output.schema.json",
        "schemas/qualification_details.schema.json",
    ]
    for path in paths:
        Draft202012Validator.check_schema(_load(path))
