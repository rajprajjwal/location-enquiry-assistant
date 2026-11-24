"""Shared interpretation validation.

Purpose: one import path for the rule functions the post-check and the
Pydantic path both call.
Use case: ``from copilot.validation import validate_interpretation_output``.
Example: an empty list means the object is valid.
"""

from copilot.validation.rules import (
    REQUIRED_FIELDS,
    UNKNOWN_UNENFORCED,
    Vocab,
    canonical_provider,
    compute_missing_required_fields,
    load_vocab,
    normalize_enum,
    validate_interpretation_output,
    validate_qualification,
)

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
