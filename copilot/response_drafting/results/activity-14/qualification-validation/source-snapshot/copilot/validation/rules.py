"""Pure checks for interpretation qualification and output.

Purpose: one implementation of the vocabulary, required-field, and schema
checks shared by the Pydantic path and the post-check.
Use case: ``validate_interpretation_output`` returns repair-prompt errors;
an empty list means valid. This module does not call a model.
Example: ``normalize_enum("api", "Directions")`` is ``"directions"``;
``canonical_provider("MapmyIndia")`` is ``"Mappls (MapmyIndia)"``.

JSON Schema files and ``vocab/controlled-vocabulary.json`` are the only I/O.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from functools import lru_cache
from types import MappingProxyType
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

_REPO = Path(__file__).resolve().parents[2]
_VOCAB_PATH = _REPO / "vocab" / "controlled-vocabulary.json"
_QUAL_SCHEMA_PATH = _REPO / "schemas" / "qualification_details.schema.json"
_OUTPUT_SCHEMA_PATH = (
    _REPO / "contracts" / "interpretation" / "interpretation_output.schema.json"
)

# Alias keys match mapping/map_gt.py PROVIDER_ALIASES plus
# _PROVIDER_ALIAS_EXTRA["openstreetmap"], which the mapping notes also list.
# Targets are the six canonical provider names. Lookup is casefold after
# strip and internal-whitespace collapse, the same steps as _canon_provider.
_PROVIDER_ALIASES: Mapping[str, str] = {
    "google": "Google Maps Platform",
    "google maps": "Google Maps Platform",
    "google maps platform": "Google Maps Platform",
    "ola": "Ola Maps",
    "ola maps": "Ola Maps",
    "mapbox": "Mapbox",
    "nominatim": "OSM Nominatim",
    "osm nominatim": "OSM Nominatim",
    "osm": "OSM Nominatim",
    "openstreetmap": "OSM Nominatim",
    "osrm": "OSRM",
    "osrm (openstreetmap)": "OSRM",
    "mappls": "Mappls (MapmyIndia)",
    "mapmyindia": "Mappls (MapmyIndia)",
    "mappls (mapmyindia)": "Mappls (MapmyIndia)",
}

_ENUM_KINDS = ("intent", "sub_intent", "api", "team")

# jsonschema 4.26 keyword -> stable repair code. Unknown keywords become
# UPPER_SNAKE of the keyword so a new keyword still has a stable shape.
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

# Spec and provider docs do not define these. They are not enforced.
UNKNOWN_UNENFORCED: tuple[str, ...] = (
    "coordinate semantics: latitude/longitude range, precision, and whether a point lies in a region are not defined on qualification_details or the interpretation contract",
    "scoring null-likes (empty string, whitespace, 'n/a', 'unknown', 'none') are defined for the scorer norm(), not for missing-field computation; only JSON null counts as missing",
    "field_provenance keys are not restricted to qualification field names",
    "trace count fields have no stated minimum; negative integers are accepted",
    "trace.model and trace.prompt_version are examples, not consts; any string is accepted",
    "rule_model_disagreements items have no closed vocabulary and no uniqueness constraint",
    "whitespace-only query or turn text of length >= 1 is accepted; no trim rule is defined",
)

_ABSENT = object()
_REQUIRED_MESSAGE = re.compile(r"'([^']+)' is a required property")


class Vocab:
    """Controlled vocabulary the interpretation step is allowed to emit.

    ``provider_aliases`` is the canonical-provider map. It is not a key of
    ``vocab/controlled-vocabulary.json`` (``provider_merges`` there is empty);
    the keys come from ``mapping/map_gt.py``.
    """

    __slots__ = (
        "intents",
        "sub_intents",
        "intent_to_sub_intents",
        "apis",
        "teams",
        "providers",
        "provider_aliases",
    )

    def __init__(
        self,
        *,
        intents: tuple[str, ...],
        sub_intents: tuple[str, ...],
        intent_to_sub_intents: Mapping[str, tuple[str, ...]],
        apis: tuple[str, ...],
        teams: tuple[str, ...],
        providers: tuple[str, ...],
        provider_aliases: Mapping[str, str],
    ) -> None:
        self.intents = intents
        self.sub_intents = sub_intents
        self.intent_to_sub_intents = intent_to_sub_intents
        self.apis = apis
        self.teams = teams
        self.providers = providers
        self.provider_aliases = provider_aliases


def _vocab_document() -> dict[str, Any]:
    return json.loads(_VOCAB_PATH.read_text(encoding="utf-8"))


def load_vocab() -> Vocab:
    """Load intents, APIs, teams, providers, and provider aliases."""
    data = _vocab_document()
    intent_map = {
        str(intent): tuple(str(item) for item in subs)
        for intent, subs in data["intent_to_sub_intents"].items()
    }
    return Vocab(
        intents=tuple(str(item) for item in data["intents"]),
        sub_intents=tuple(str(item) for item in data["sub_intents"]),
        intent_to_sub_intents=MappingProxyType(intent_map),
        apis=tuple(str(item) for item in data["apis"]),
        teams=tuple(str(item) for item in data["teams"]),
        providers=tuple(str(item) for item in data["providers"]),
        provider_aliases=MappingProxyType(dict(_PROVIDER_ALIASES)),
    )


REQUIRED_FIELDS: tuple[str, ...] = tuple(
    str(item) for item in _vocab_document()["qualification_required_fields"]
)


def normalize_enum(
    kind: Literal["intent", "sub_intent", "api", "team"],
    value: str | None,
) -> str | None:
    """Return the vocabulary spelling of ``value``, or None.

    Match is casefold equality with a vocabulary entry and nothing else:
    no trim, no alias table, no NFKC. ``None`` and any non-string are None.
    A string that is not in the vocabulary is None; nothing is guessed.
    """
    if kind not in _ENUM_KINDS:
        raise ValueError(f"unknown enum kind: {kind!r}")
    if not isinstance(value, str):
        return None
    folded = value.casefold()
    vocab = load_vocab()
    table = {
        "intent": vocab.intents,
        "sub_intent": vocab.sub_intents,
        "api": vocab.apis,
        "team": vocab.teams,
    }[kind]
    for item in table:
        if item.casefold() == folded:
            return item
    return None


def canonical_provider(value: str | None) -> str | None:
    """Map a provider string through ``PROVIDER_ALIASES``, or return None.

    The key is ``value`` stripped, with internal whitespace collapsed, then
    casefolded. Unknown strings, ``None``, and non-strings return None.
    """
    if not isinstance(value, str):
        return None
    key = re.sub(r"\s+", " ", value.strip()).casefold()
    return _PROVIDER_ALIASES.get(key)


def compute_missing_required_fields(qual: dict) -> list[str]:
    """Required fields whose value is None, in vocabulary order.

    Only the values are read. A declared ``missing_required_fields`` list
    is ignored. A value that is not None (including ``""``, whitespace,
    and ``"n/a"``) is present. See ``UNKNOWN_UNENFORCED``.
    """
    if not isinstance(qual, dict):
        raise TypeError("qual must be a dict")
    return [field for field in REQUIRED_FIELDS if qual.get(field) is None]


def validate_qualification(qual: dict) -> list[str]:
    """Schema-check a qualification object and its consistency rules.

    Schema errors come first, sorted by JSON Pointer, then rule code, then
    detail. Consistency checks then run in a fixed order:
    ``MISSING_REQUIRED_FIELDS``, ``COMPLETE_FLAG``.
    """
    errors = _schema_errors(qual, _qualification_validator())
    if isinstance(qual, dict):
        errors.extend(_format(_qualification_consistency(qual)))
    return errors


def validate_interpretation_output(obj: dict) -> list[str]:
    """Schema-check an interpretation output plus the shared qual checks.

    After the qualification consistency checks, output checks run in this
    order: ``API_MISMATCH`` (null ``api`` with null ``use_case_api`` agrees),
    ``MISSING_FIELDS_MISMATCH``, ``ABSTAIN_REQUIRED_FIELDS`` (abstain false
    requires intent, api and team in the vocabulary), then
    ``ABSTAIN_REASON_REQUIRED`` (abstain true requires a non-empty reason),
    then ``ABSTAIN_REASON_FORBIDDEN`` (abstain false requires a null reason).
    """
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
    errors.extend(_format(_abstain_reason_forbidden(obj)))
    return errors


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
    expected_complete = len(computed) == 0
    actual_complete = qual.get("complete", _ABSENT)
    if actual_complete is not expected_complete:
        rows.append(
            (
                "/complete",
                "COMPLETE_FLAG",
                f"complete={_fmt(actual_complete)} expected={_fmt(expected_complete)}",
            )
        )
    return rows


def _api_mismatch(obj: dict) -> list[tuple[str, str, str]]:
    top = obj.get("api", _ABSENT)
    qual = obj.get("qualification_details", _ABSENT)
    pointer = "/qualification_details/use_case_api/api"
    if not isinstance(qual, dict):
        return [
            (
                pointer,
                "API_MISMATCH",
                f"qualification_details={_fmt(qual)} api={_fmt(top)}",
            )
        ]
    use_case_api = qual.get("use_case_api", _ABSENT)
    # v0.2.0: a null api is consistent with a null use_case_api. That null
    # counts as missing via compute_missing_required_fields; it is not a mismatch.
    if use_case_api is None and top is None:
        return []
    if not isinstance(use_case_api, dict):
        return [
            (
                pointer,
                "API_MISMATCH",
                f"use_case_api={_fmt(use_case_api)} api={_fmt(top)}",
            )
        ]
    got = use_case_api.get("api", _ABSENT)
    if got != top:
        return [
            (
                pointer,
                "API_MISMATCH",
                f"use_case_api.api={_fmt(got)} api={_fmt(top)}",
            )
        ]
    return []


def _missing_list_mismatch(obj: dict) -> list[tuple[str, str, str]]:
    top = obj.get("missing_required_fields", _ABSENT)
    qual = obj.get("qualification_details", _ABSENT)
    if isinstance(qual, dict):
        nested = qual.get("missing_required_fields", _ABSENT)
    else:
        nested = _ABSENT
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


def _abstain_reason_forbidden(obj: dict) -> list[tuple[str, str, str]]:
    """abstain false requires abstain_reason to be JSON null.

    The key is in the schema required list, so a missing key is not null.
    Values are not trimmed.
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


def _schema_errors(instance: object, validator: Draft202012Validator) -> list[str]:
    rows: list[tuple[str, str, str]] = []
    for error in validator.iter_errors(instance):
        rows.append((_pointer(error), _schema_code(error.validator), error.message))
    rows.sort()
    unique: list[tuple[str, str, str]] = []
    for row in rows:
        if not unique or unique[-1] != row:
            unique.append(row)
    return _format(unique)


def _schema_code(keyword: object) -> str:
    if isinstance(keyword, str) and keyword in _SCHEMA_CODES:
        return _SCHEMA_CODES[keyword]
    text = str(keyword)
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return snake.upper()


def _pointer(error: ValidationError) -> str:
    parts = [_pointer_token(part) for part in error.absolute_path]
    if error.validator == "required":
        match = _REQUIRED_MESSAGE.fullmatch(error.message)
        if match:
            parts.append(_pointer_token(match.group(1)))
    if not parts:
        return ""
    return "/" + "/".join(parts)


def _pointer_token(part: object) -> str:
    if isinstance(part, int):
        return str(part)
    return str(part).replace("~", "~0").replace("/", "~1")


def _prefix(base: str, pointer: str) -> str:
    if pointer == "":
        return base
    return base + pointer


def _format(rows: list[tuple[str, str, str]]) -> list[str]:
    return [f"{pointer}: {code}: {detail}" for pointer, code, detail in rows]


def _fmt(value: object) -> str:
    if value is _ABSENT:
        return "<absent>"
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


@lru_cache(maxsize=1)
def _qualification_validator() -> Draft202012Validator:
    schema = json.loads(_QUAL_SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


@lru_cache(maxsize=1)
def _output_validator() -> Draft202012Validator:
    schema = json.loads(_OUTPUT_SCHEMA_PATH.read_text(encoding="utf-8"))
    qual = json.loads(_QUAL_SCHEMA_PATH.read_text(encoding="utf-8"))
    resource = Resource.from_contents(qual, default_specification=DRAFT202012)
    registry: Registry = Registry().with_resource(qual["$id"], resource)
    return Draft202012Validator(schema, registry=registry)


__all__ = [
    "REQUIRED_FIELDS",
    "UNKNOWN_UNENFORCED",
    "Vocab",
    "canonical_provider",
    "compute_missing_required_fields",
    "load_vocab",
    "normalize_enum",
    "validate_interpretation_output",
    "validate_qualification",
]
