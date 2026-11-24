"""Typed customer requirements shared by interpretation and follow-up planning."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from copilot.diagnostics.facts import DiagnosticFact

FactId = Literal[
    'region', 'monthly_volume', 'peak_rate', 'timeline', 'sla', 'budget',
    'current_provider', 'alternative_providers', 'backend_owner', 'deployment_owner',
    'hosting_preference', 'billing_country', 'usage_geography', 'billing_basis',
    'billing_account_scope', 'commercial_plan', 'existing_project', 'api_enabled',
    'details_completion', 'details_sku', 'debouncing', 'session_tokens',
    'traffic_required', 'traffic_scope', 'departure_time_mode', 'travel_mode',
    'max_stops', 'hazmat_required', 'vehicle_dimensions', 'instruction_modality',
    'origin_count', 'destination_count', 'input_type', 'matrix_frequency',
    'peak_concurrency', 'mapbox_traffic_profile', 'requests_splittable',
    'storage_required', 'retention_period', 'redistribution_required', 'resale_required',
    'display_context', 'lookup_trigger', 'languages', 'public_service_acceptable',
    'temporary_results_acceptable', 'rooftop_hard_filter', 'address_elements_required',
]


class QualificationContext(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal['1.0'] = '1.0'
    api: str
    intent: str
    facts: dict[FactId, DiagnosticFact] = Field(default_factory=dict)
    missing_interpretation_fields: list[str] = Field(default_factory=list)


class SuppliedFact(BaseModel):
    model_config = ConfigDict(extra='forbid')
    field: FactId
    value: str | bool | int | float
    evidence: str = Field(min_length=1, max_length=500)


class QuestionGroup(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fields: list[FactId] = Field(min_length=1, max_length=8)
    decision_impact: str = Field(min_length=1, max_length=450)


class QualificationPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    supplied_facts: list[SuppliedFact] = Field(default_factory=list, max_length=32)
    groups: list[QuestionGroup] = Field(default_factory=list, max_length=10)
    reason: str = Field(min_length=1, max_length=600)
