"""Resolve one requirement plan for staff questions and checklist advice."""
from pydantic import BaseModel, ConfigDict, Field

from .contract import FactId, QuestionGroup
from .wording import render


class RequirementDecision(QuestionGroup):
    question: str
    required_by: str


class RequirementPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: str = '1.0'
    task: str
    decisions: list[RequirementDecision] = Field(default_factory=list)
    omitted: list[dict] = Field(default_factory=list)


def available_fields(context, state):
    available = {field for field, fact in context.facts.items()
                 if fact.status in {'asked', 'declined', 'documentation'}
                 or fact.status == 'supplied' and fact.value is not None}
    available.update(context.assumptions)
    available.update(context.blocked_fields)
    for values in (context.facts, context.assumptions):
        volume = values.get('monthly_volume')
        if volume and isinstance(volume.value, dict) and volume.value.get('unit') == 'matrices_per_month':
            available.add('matrices_per_month')
    return available


def requirement_plan(context, state, candidates, task, *, selected_fields=None, checklist=False):
    """A model selects conditional decisions; an explicit checklist retains its requested scope."""
    available = available_fields(context, state)
    selected = set()
    decisions, omitted = [], []
    for candidate in candidates:
        group = QuestionGroup.model_validate({key: candidate[key] for key in ('fields', 'decision_impact')})
        required = checklist or candidate.get('required', False)
        if not required and selected_fields is not None and not set(group.fields).intersection(selected_fields):
            omitted.append({'fields': group.fields, 'reason': 'No material decision selected.'})
            continue
        missing = [field for field in dict.fromkeys(group.fields) if field not in available and field not in selected]
        if not missing:
            omitted.append({'fields': group.fields, 'reason': 'Already supplied, assumed, asked or declined.'})
            continue
        selected.update(missing)
        decisions.append(RequirementDecision(fields=missing, decision_impact=group.decision_impact,
            question=render(missing), required_by='required_customer_decision' if required else 'selected_decision'))
    return RequirementPlan(task=task, decisions=decisions, omitted=omitted)
