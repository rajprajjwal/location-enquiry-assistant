"""TEST-ONLY fake of ``copilot.models`` and ``copilot.validation.rules``.

Purpose: stand in for the Knowledge & Validation package during unit tests.
Use case: ``tests/conftest.py`` installs this onto ``copilot.enquiry_interpretation.seam``.
Example: ``normalize_enum("api", "Directions")`` is ``"directions"``.

This is not production code and it is not a copy of ``copilot/validation/rules.py``.
It reads ``vocab/controlled-vocabulary.json`` and
``schemas/qualification_details.schema.json``, and it checks the v0.2.0
wrapper shape: ``intent``, ``api`` and ``team`` may be JSON null, and a null
``api`` with a null ``use_case_api`` is consistent. Do not import it from
``copilot/``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from mapping.map_gt import PROVIDER_ALIASES

_REPO = Path(__file__).resolve().parents[2]
_VOCAB_PATH = _REPO / "vocab" / "controlled-vocabulary.json"
_QUAL_PATH = _REPO / "schemas" / "qualification_details.schema.json"

# INTERFACE.md: map_gt PROVIDER_ALIASES plus openstreetmap → OSM Nominatim.
_ALIASES = dict(PROVIDER_ALIASES)
_ALIASES["openstreetmap"] = "OSM Nominatim"

_ENUM_KINDS = {
    "intent": "intents",
    "sub_intent": "sub_intents",
    "api": "apis",
    "team": "teams",
}
_SCHEMA_CODES = {
    "additionalProperties": "ADDITIONAL_PROPERTIES",
    "allOf": "ALL_OF",
    "anyOf": "ANY_OF",
    "const": "CONST",
    "contains": "CONTAINS",
    "dependentRequired": "DEPENDENT_REQUIRED",
    "enum": "ENUM",
    "exclusiveMaximum": "EXCLUSIVE_MAXIMUM",
    "exclusiveMinimum": "EXCLUSIVE_MINIMUM",
    "format": "FORMAT",
    "maxItems": "MAX_ITEMS",
    "maxLength": "MAX_LENGTH",
    "maxProperties": "MAX_PROPERTIES",
    "maximum": "MAXIMUM",
    "minItems": "MIN_ITEMS",
    "minLength": "MIN_LENGTH",
    "minProperties": "MIN_PROPERTIES",
    "minimum": "MINIMUM",
    "multipleOf": "MULTIPLE_OF",
    "not": "NOT",
    "oneOf": "ONE_OF",
    "pattern": "PATTERN",
    "prefixItems": "PREFIX_ITEMS",
    "required": "REQUIRED",
    "type": "TYPE",
    "uniqueItems": "UNIQUE_ITEMS",
}
_REQUIRED_MESSAGE = re.compile(r"'([^']+)' is a required property")
_ABSENT = object()


class Vocab:
    """Vocabulary view. Attribute names match ``copilot.validation.rules.Vocab``."""

    def __init__(self, data: dict):
        self.intents = tuple(data["intents"])
        self.sub_intents = tuple(data["sub_intents"])
        self.apis = tuple(data["apis"])
        self.teams = tuple(data["teams"])
        self.providers = tuple(data["providers"])
        self.intent_to_sub_intents = MappingProxyType(
            {
                str(intent): tuple(str(item) for item in subs)
                for intent, subs in data["intent_to_sub_intents"].items()
            }
        )
        self.provider_aliases = MappingProxyType(dict(_ALIASES))


def load_vocab() -> Vocab:
    data = json.loads(_VOCAB_PATH.read_text(encoding="utf-8"))
    return Vocab(data)


REQUIRED_FIELDS: tuple[str, ...] = tuple(
    json.loads(_VOCAB_PATH.read_text(encoding="utf-8"))["qualification_required_fields"]
)


def normalize_enum(kind: str, value: Any) -> str | None:
    """Case-folded exact match. No trim and no guessing."""
    if kind not in _ENUM_KINDS:
        raise ValueError(f"unknown enum kind: {kind}")
    if not isinstance(value, str):
        return None
    folded = value.casefold()
    table = getattr(load_vocab(), _ENUM_KINDS[kind])
    for item in table:
        if item.casefold() == folded:
            return item
    return None


def canonical_provider(value: Any) -> str | None:
    """Strip, collapse whitespace, casefold, then alias lookup."""
    if not isinstance(value, str):
        return None
    key = re.sub(r"\s+", " ", value.strip()).casefold()
    return _ALIASES.get(key)


def compute_missing_required_fields(qual: dict) -> list[str]:
    """Required fields whose value is JSON null, in vocabulary order."""
    if not isinstance(qual, dict):
        raise TypeError("qual must be a dict")
    return [field for field in REQUIRED_FIELDS if qual.get(field) is None]


def _fmt(value: object) -> str:
    if value is _ABSENT:
        return "<absent>"
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _schema_code(keyword: object) -> str:
    if isinstance(keyword, str) and keyword in _SCHEMA_CODES:
        return _SCHEMA_CODES[keyword]
    text = str(keyword)
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return snake.upper()


def _pointer_token(part: object) -> str:
    if isinstance(part, int):
        return str(part)
    return str(part).replace("~", "~0").replace("/", "~1")


def _pointer(error: ValidationError) -> str:
    parts = [_pointer_token(part) for part in error.absolute_path]
    if error.validator == "required":
        match = _REQUIRED_MESSAGE.fullmatch(error.message)
        if match:
            parts.append(_pointer_token(match.group(1)))
    if not parts:
        return ""
    return "/" + "/".join(parts)


def _format(rows: list[tuple[str, str, str]]) -> list[str]:
    return [f"{pointer}: {code}: {detail}" for pointer, code, detail in rows]


def _schema_errors(instance: object, validator: Draft202012Validator) -> list[str]:
    rows = [
        (_pointer(error), _schema_code(error.validator), error.message)
        for error in validator.iter_errors(instance)
    ]
    rows.sort()
    unique: list[tuple[str, str, str]] = []
    for row in rows:
        if not unique or unique[-1] != row:
            unique.append(row)
    return _format(unique)


def _qualification_consistency(qual: dict) -> list[tuple[str, str, str]]:
    computed = compute_missing_required_fields(qual)
    declared = qual.get("missing_required_fields", _ABSENT)
    rows: list[tuple[str, str, str]] = []
    if declared != computed:
        rows.append(
            (
                "/missing_required_fields",
                "MISSING_REQUIRED_FIELDS",
                f"declared={_fmt(declared)} computed={_fmt(computed)}",
            )
        )
    expected = len(computed) == 0
    actual = qual.get("complete", _ABSENT)
    if actual is not expected:
        rows.append(
            (
                "/complete",
                "COMPLETE_FLAG",
                f"complete={_fmt(actual)} expected={_fmt(expected)}",
            )
        )
    return rows


def _prefix(base: str, pointer: str) -> str:
    if pointer == "":
        return base
    return base + pointer


def _load_qual_schema() -> dict:
    return json.loads(_QUAL_PATH.read_text(encoding="utf-8"))


def _qualification_validator() -> Draft202012Validator:
    return Draft202012Validator(_load_qual_schema())


def _output_schema() -> dict:
    vocab = load_vocab()
    qual_id = _load_qual_schema()["$id"]
    sub_enum: list[Any] = list(vocab.sub_intents) + [None]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://capstone.local/lbs-copilot/contracts/interpretation_output/v0.2.0",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "intent",
            "sub_intent",
            "api",
            "team",
            "qualification_details",
            "missing_required_fields",
            "field_provenance",
            "confidence",
            "abstain",
            "abstain_reason",
            "trace",
        ],
        "properties": {
            "intent": {"type": ["string", "null"], "enum": list(vocab.intents) + [None]},
            "sub_intent": {"type": ["string", "null"], "enum": sub_enum},
            "api": {"type": ["string", "null"], "enum": list(vocab.apis) + [None]},
            "team": {"type": ["string", "null"], "enum": list(vocab.teams) + [None]},
            "qualification_details": {"$ref": qual_id},
            "missing_required_fields": {
                "type": "array",
                "items": {"type": "string", "enum": list(REQUIRED_FIELDS)},
                "uniqueItems": True,
            },
            "field_provenance": {
                "type": "object",
                "additionalProperties": {
                    "type": "string",
                    "enum": ["rule", "model", "history", "state"],
                },
            },
            "confidence": {
                "type": "object",
                "additionalProperties": False,
                "required": ["intent", "api", "team"],
                "properties": {
                    "intent": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                    "api": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                    "team": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                },
            },
            "abstain": {"type": "boolean"},
            "abstain_reason": {
                "type": ["string", "null"],
                "enum": [
                    "model_unavailable",
                    "invalid_after_repair",
                    "budget_exceeded",
                    "no_rule_match",
                    None,
                ],
            },
            "trace": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "model",
                    "prompt_version",
                    "approx_input_tokens",
                    "approx_output_tokens",
                    "latency_ms",
                    "repair_attempts",
                    "model_calls",
                    "rule_model_disagreements",
                ],
                "properties": {
                    "model": {"type": "string"},
                    "prompt_version": {"type": "string"},
                    "approx_input_tokens": {"type": "integer"},
                    "approx_output_tokens": {"type": "integer"},
                    "latency_ms": {"type": "integer"},
                    "repair_attempts": {"type": "integer"},
                    "model_calls": {"type": "integer"},
                    "rule_model_disagreements": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "allOf": [
            {
                "if": {
                    "properties": {"abstain": {"const": False}},
                    "required": ["abstain"],
                },
                "then": {
                    "properties": {
                        "intent": {"type": "string", "enum": list(vocab.intents)},
                        "api": {"type": "string", "enum": list(vocab.apis)},
                        "team": {"type": "string", "enum": list(vocab.teams)},
                        "abstain_reason": {"const": None},
                    },
                    "required": ["intent", "api", "team", "abstain_reason"],
                },
            },
            {
                "if": {
                    "properties": {"abstain": {"const": True}},
                    "required": ["abstain"],
                },
                "then": {
                    "properties": {
                        "abstain_reason": {
                            "type": "string",
                            "minLength": 1,
                            "enum": [
                                "model_unavailable",
                                "invalid_after_repair",
                                "budget_exceeded",
                                "no_rule_match",
                            ],
                        },
                    },
                    "required": ["abstain_reason"],
                },
            },
        ],
    }


def _output_validator() -> Draft202012Validator:
    qual = _load_qual_schema()
    resource = Resource.from_contents(qual, default_specification=DRAFT202012)
    registry: Registry = Registry().with_resource(qual["$id"], resource)
    return Draft202012Validator(_output_schema(), registry=registry)


def validate_qualification(qual: dict) -> list[str]:
    errors = _schema_errors(qual, _qualification_validator())
    if isinstance(qual, dict):
        errors.extend(_format(_qualification_consistency(qual)))
    return errors


def _api_mismatch(obj: dict) -> list[tuple[str, str, str]]:
    top = obj.get("api", _ABSENT)
    qual = obj.get("qualification_details", _ABSENT)
    pointer = "/qualification_details/use_case_api/api"
    if not isinstance(qual, dict):
        return [(pointer, "API_MISMATCH", f"qualification_details={_fmt(qual)} api={_fmt(top)}")]
    use_case_api = qual.get("use_case_api", _ABSENT)
    # v0.2.0: a null api and a null use_case_api are the same fact.
    if use_case_api is None and top is None:
        return []
    if not isinstance(use_case_api, dict):
        return [(pointer, "API_MISMATCH", f"use_case_api={_fmt(use_case_api)} api={_fmt(top)}")]
    got = use_case_api.get("api", _ABSENT)
    if got != top:
        return [(pointer, "API_MISMATCH", f"use_case_api.api={_fmt(got)} api={_fmt(top)}")]
    return []


def _missing_list_mismatch(obj: dict) -> list[tuple[str, str, str]]:
    top = obj.get("missing_required_fields", _ABSENT)
    qual = obj.get("qualification_details", _ABSENT)
    nested = qual.get("missing_required_fields", _ABSENT) if isinstance(qual, dict) else _ABSENT
    if top == nested:
        return []
    return [
        (
            "/missing_required_fields",
            "MISSING_FIELDS_MISMATCH",
            "missing_required_fields="
            f"{_fmt(top)} qualification_details.missing_required_fields={_fmt(nested)}",
        )
    ]


_ABSTAIN_VALUE_FIELDS = ("intent", "api", "team")


def _abstain_required_fields(obj: dict) -> list[tuple[str, str, str]]:
    """abstain false requires intent, api and team to be vocabulary values."""
    if obj.get("abstain") is not False:
        return []
    vocab = load_vocab()
    tables = {"intent": vocab.intents, "api": vocab.apis, "team": vocab.teams}
    rows: list[tuple[str, str, str]] = []
    for field in _ABSTAIN_VALUE_FIELDS:
        value = obj.get(field, _ABSENT)
        if isinstance(value, str) and value in tables[field]:
            continue
        rows.append(
            (
                f"/{field}",
                "ABSTAIN_REQUIRED_FIELDS",
                f"abstain=false requires {field} in the controlled vocabulary; "
                f"{field}={_fmt(value)}",
            )
        )
    return rows


def _abstain_reason_required(obj: dict) -> list[tuple[str, str, str]]:
    """abstain true requires a reason string that is not empty or whitespace."""
    if obj.get("abstain") is not True:
        return []
    reason = obj.get("abstain_reason", _ABSENT)
    if isinstance(reason, str) and reason.strip():
        return []
    return [
        (
            "/abstain_reason",
            "ABSTAIN_REASON_REQUIRED",
            "abstain=true requires a non-empty abstain_reason; "
            f"abstain_reason={_fmt(reason)}",
        )
    ]


def _abstain_reason_must_be_null(obj: dict) -> list[tuple[str, str, str]]:
    """abstain false requires the abstain_reason key to be present and JSON null.

    A missing key is not null. The schema also reports REQUIRED or CONST.
    """
    if obj.get("abstain") is not False:
        return []
    reason = obj.get("abstain_reason", _ABSENT)
    if reason is None:
        return []
    return [
        (
            "/abstain_reason",
            "ABSTAIN_REASON_FORBIDDEN",
            "abstain=false requires abstain_reason null; "
            f"abstain_reason={_fmt(reason)}",
        )
    ]


def validate_interpretation_output(obj: dict) -> list[str]:
    errors = _schema_errors(obj, _output_validator())
    if not isinstance(obj, dict):
        return errors
    qual = obj.get("qualification_details")
    if isinstance(qual, dict):
        for pointer, code, detail in _qualification_consistency(qual):
            errors.append(f"{_prefix('/qualification_details', pointer)}: {code}: {detail}")
    errors.extend(_format(_api_mismatch(obj)))
    errors.extend(_format(_missing_list_mismatch(obj)))
    errors.extend(_format(_abstain_required_fields(obj)))
    errors.extend(_format(_abstain_reason_required(obj)))
    errors.extend(_format(_abstain_reason_must_be_null(obj)))
    return errors


class _Model:
    def __init__(self, **data):
        self._data = data
        for key, value in data.items():
            setattr(self, key, value)

    def model_dump(self, mode: str = "python") -> dict:
        return json.loads(json.dumps(self._data))

    @classmethod
    def model_validate(cls, data):
        if isinstance(data, cls):
            return data
        if hasattr(data, "model_dump"):
            data = data.model_dump(mode="json")
        if not isinstance(data, dict):
            raise TypeError("expected an object")
        return cls(**data)


class InterpretationInput(_Model):
    @classmethod
    def model_validate(cls, data):
        if isinstance(data, cls):
            return data
        if hasattr(data, "model_dump"):
            data = data.model_dump(mode="json")
        if not isinstance(data, dict):
            raise TypeError("expected an object")
        query = data.get("query")
        if not isinstance(query, str) or len(query) < 1:
            raise ValueError("query must be a non-empty string")
        return cls(
            query=query,
            history=list(data.get("history") or []),
            known_facts=list(data.get("known_facts") or []),
            record_id=data.get("record_id"),
        )


class InterpretationOutput(_Model):
    pass


class Turn(_Model):
    pass


class KnownFact(_Model):
    pass


class QualificationDetails(_Model):
    pass


def models():
    return SimpleNamespace(
        InterpretationInput=InterpretationInput,
        InterpretationOutput=InterpretationOutput,
        KnownFact=KnownFact,
        QualificationDetails=QualificationDetails,
        Turn=Turn,
    )


def install(seam_module) -> None:
    """Replace the production seam with this fake. Tests only."""
    seam_module.load_vocab = load_vocab
    seam_module.normalize_enum = normalize_enum
    seam_module.canonical_provider = canonical_provider
    seam_module.REQUIRED_FIELDS = REQUIRED_FIELDS
    seam_module.compute_missing_required_fields = compute_missing_required_fields
    seam_module.validate_qualification = validate_qualification
    seam_module.validate_interpretation_output = validate_interpretation_output
    seam_module.models = models
