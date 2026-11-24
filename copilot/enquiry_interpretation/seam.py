"""Single import seam for the shared models and validation rules.

Purpose: production interpretation code reaches ``copilot.models`` and
``copilot.validation.rules`` only through this module.
Use case: tests replace these callables with the test-only fake under ``tests/``.
Example: ``seam.normalize_enum("api", "Directions")`` returns ``"directions"``
once the validation package (or the test fake) is installed.
``load_vocab()`` returns a ``Vocab`` object. Validate with
``validate_*(model.model_dump(mode="json"))``.

The Knowledge & Validation package owns the implementations. This module does
not define vocabularies, schemas, or Pydantic models.
"""

from __future__ import annotations

from typing import Any, Literal

EnumKind = Literal["intent", "sub_intent", "api", "team"]


def _rules():
    try:
        from copilot.validation import rules as rules_mod
    except ImportError as exc:  # pragma: no cover - exercised when the package is absent
        raise ImportError(
            "copilot.validation.rules is provided by the Knowledge & Validation "
            "package and is not installed in this checkout"
        ) from exc
    return rules_mod


def models():
    """Return the ``copilot.models`` module (generated Pydantic models)."""
    try:
        import copilot.models as models_mod
    except ImportError as exc:  # pragma: no cover - exercised when the package is absent
        raise ImportError(
            "copilot.models is provided by the Knowledge & Validation package "
            "and is not installed in this checkout"
        ) from exc
    return models_mod


def load_vocab() -> dict:
    return _rules().load_vocab()


def normalize_enum(kind: EnumKind, value: Any) -> str | None:
    return _rules().normalize_enum(kind, value)


def canonical_provider(value: Any) -> str | None:
    return _rules().canonical_provider(value)


def compute_missing_required_fields(qual: dict) -> list[str]:
    return list(_rules().compute_missing_required_fields(qual))


def validate_qualification(qual: dict) -> list[str]:
    return list(_rules().validate_qualification(qual))


def validate_interpretation_output(obj: dict) -> list[str]:
    return list(_rules().validate_interpretation_output(obj))


def __getattr__(name: str):
    if name == "REQUIRED_FIELDS":
        return _rules().REQUIRED_FIELDS
    raise AttributeError(name)
