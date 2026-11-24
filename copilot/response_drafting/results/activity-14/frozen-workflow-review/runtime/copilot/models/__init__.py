"""Pydantic models for the interpretation step.

Purpose: re-export the generated interpretation models (output contract v0.2.0).
Use case: ``from copilot.models import InterpretationInput, InterpretationOutput``.
Example: ``QualificationDetails`` is generated from
``schemas/qualification_details.schema.json``.

The modules under ``generated/`` are produced by ``scripts/gen_models.py``.
Do not hand-edit them. Structural checks (types, enums, required keys,
``extra='forbid'``) live on these models. Consistency checks live in
``copilot.validation.rules`` and are not copied here.
"""

from copilot.models.generated.interpretation_input import InterpretationInput
from copilot.models.generated.interpretation_output import (
    Confidence,
    InterpretationOutput,
    Trace,
)
from copilot.models.generated.known_fact import KnownFact
from copilot.models.generated.qualification_details import (
    MonthlyVolume,
    QualificationDetails,
    UseCaseApi,
)
from copilot.models.generated.turn import Turn

__all__ = [
    "Confidence",
    "InterpretationInput",
    "InterpretationOutput",
    "KnownFact",
    "MonthlyVolume",
    "QualificationDetails",
    "Trace",
    "Turn",
    "UseCaseApi",
]
