"""Shared diagnostic facts, provenance and question lifecycle for one case."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .extraction import extract_supplied_facts
from copilot.safety.provider_evidence import current_provider_revoked

QUALIFICATION_FIELDS = {"use_case_api", "region", "monthly_volume", "current_provider", "timeline",
                        "budget", "technical_constraints", "decision_maker"}


class DiagnosticFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    status: Literal["supplied", "missing", "asked", "declined", "documentation"] = "supplied"
    value: Any = None
    source: str = "query"
    evidence: str = ""
    start: int | None = None
    end: int | None = None


class DiagnosticQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    facts: list[str]
    text: str
    status: Literal["suggested", "asked", "answered", "declined"] = "suggested"


class DiagnosticState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["1.0"] = "1.0"
    facts: dict[str, DiagnosticFact] = Field(default_factory=dict)
    questions: list[DiagnosticQuestion] = Field(default_factory=list)
    completed_checks: list[str] = Field(default_factory=list)


def build_diagnostic_state(enquiry, previous=None):
    state = DiagnosticState.model_validate(previous or {}).model_copy(deep=True)
    if "known_facts" in enquiry:
        current = {fact["field"] for fact in enquiry["known_facts"]}
        for field in QUALIFICATION_FIELDS - current:
            state.facts.pop(field, None)
    for fact in enquiry.get("known_facts", []):
        if fact.get("field") and fact.get("value") is not None:
            state.facts[fact["field"]] = DiagnosticFact(
                field=fact["field"], value=fact["value"], source=fact.get("source", "state_store"),
            )
    extracted = extract_supplied_facts(enquiry)
    mentions = next((fact for fact in extracted if fact['field'] == 'mentioned_providers'), None)
    if mentions and len(mentions['value']) != 1:
        state.facts.pop('provider', None)
    for fact in extracted:
        if fact['field'] == 'current_provider' and fact['source'] != 'query' and any(
            known.get('field') == 'current_provider' and known.get('value') is not None
            for known in enquiry.get('known_facts', [])
        ):
            # Stored confirmation is newer than its original history assertion.
            continue
        state.facts[fact["field"]] = DiagnosticFact(**fact)
    previous_provider = state.facts.get('current_provider')
    if previous_provider and current_provider_revoked(enquiry, previous_provider.value,
        trusted_confirmation=any(fact.get('field') == 'current_provider' and fact.get('value') == previous_provider.value
                                 for fact in enquiry.get('known_facts', []))):
        state.facts.pop('current_provider', None)
    for question in state.questions:
        if question.status == "asked" and all(
            state.facts.get(field) and state.facts[field].status == "supplied" for field in question.facts
        ):
            question.status = "answered"
    return state


def qualification_facts(state):
    """Adapt shared facts to the existing interpretation input contract."""
    return [
        {"field": fact.field, "value": fact.value, "source": "history"}
        for fact in state.facts.values()
        if fact.field in QUALIFICATION_FIELDS and fact.status == "supplied" and fact.value is not None
    ]
