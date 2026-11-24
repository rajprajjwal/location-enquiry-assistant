"""Pydantic input and result contracts for the registered app tools."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

Text = Annotated[str, Field(min_length=1)]
Positive = Annotated[int, Field(gt=0)]
Count = Annotated[int, Field(ge=0)]
API = Literal["directions", "distance_matrix", "autocomplete", "reverse_geocode"]
Provider = Literal["Google Maps Platform", "Ola Maps", "Mapbox", "OSM Nominatim", "OSRM", "Mappls (MapmyIndia)"]
Dimension = Literal["pricing", "limits", "coverage", "capabilities"]
RecordId = Annotated[str, Field(pattern=r"^(TKT|OPP)-\d{3,8}$")]


class ToolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


ReferenceScope = Literal["directions_products", "matrix_limits", "reverse_geocoding_policy", "autocomplete_global_price"]


class SearchInput(ToolModel):
    query: Text
    max_results: Annotated[int, Field(ge=1, le=20)] = 5
    scope: ReferenceScope | None = None


class SearchHit(ToolModel):
    document_id: Text
    document_title: Text
    source_url: str
    retrieved_date: Text
    relevant_passage: str
    relevance_score: float
    document_type: Text


class SearchOutput(ToolModel):
    results: list[SearchHit]


class CalculatorInput(ToolModel):
    api: API
    monthly_usage: Annotated[float, Field(ge=0)]
    provider_plans: dict[str, JsonValue]
    region: str = "global"
    capability_matrix: dict[str, JsonValue] | None = None
    coverage_map: dict[str, JsonValue] | None = None
    limits_map: dict[str, JsonValue] | None = None
    assumptions: list[str] | None = None


class CalculatorOutput(ToolModel):
    requested_api: API
    providers: list[Text]
    comparison_id: str | None = None
    geographic_region: str | None = None
    monthly_usage: float | None = None
    monthly_usage_unit: str | None = None
    calculated_costs: dict[str, float | None] | None = None
    pricing_details: dict[str, JsonValue] | None = None
    capability_differences: dict[str, JsonValue] | None = None
    coverage_differences: dict[str, JsonValue] | None = None
    limit_differences: dict[str, JsonValue] | None = None
    assumptions: list[str] | None = None
    missing_information: list[str] | None = None
    source_references: list[dict[str, str]] | None = None
    calculation_breakdown: dict[str, JsonValue] | None = None
    execution_timestamp: str | None = None


class Workload(ToolModel):
    quantity: Positive
    unit: Literal["requests", "elements", "sessions", "matrix_requests"]
    origins: Positive | None = None
    destinations: Positive | None = None
    keystrokes_per_session: Positive | None = None

    @model_validator(mode="after")
    def require_unit_specific_fields(self):
        if self.unit == "matrix_requests":
            if self.origins is None or self.destinations is None:
                raise ValueError("matrix requests require origins and destinations")
        elif self.origins is not None or self.destinations is not None:
            raise ValueError("grid dimensions require the matrix_requests unit")
        if self.keystrokes_per_session is not None and self.unit != "sessions":
            raise ValueError("keystrokes per session require the sessions unit")
        return self


class Requirements(ToolModel):
    api: API | None = None
    region: Text | None = None
    monthly_volume_raw: str | None = None
    monthly_workload: Workload | None = None


class AppComparisonInput(ToolModel):
    operation: Literal["price_quote", "combined", "matrix_limits"]
    query: Text
    providers: Annotated[list[Provider], Field(min_length=2, max_length=3)] | None = None
    requirements: Requirements | None = None
    origins: Positive | None = None
    destinations: Positive | None = None

    @model_validator(mode="after")
    def validate_operation(self):
        if self.operation == "matrix_limits":
            if self.origins is None or self.destinations is None or self.providers is not None or self.requirements is not None:
                raise ValueError("matrix limits require an origin and destination count")
            return self
        if self.origins is not None or self.destinations is not None:
            raise ValueError("matrix counts are only used for matrix limits")
        if self.operation == "combined":
            if not self.providers or len(self.providers) != len(set(self.providers)):
                raise ValueError("combined comparisons require two or three unique providers")
            scope = self.requirements
            if not scope or not (scope.api and scope.region and scope.monthly_workload):
                raise ValueError("combined comparisons require one API, region, and workload")
        elif self.providers is not None or self.requirements is not None:
            raise ValueError("price_quote takes the enquiry text")
        return self


class Reference(ToolModel):
    url: Text
    span: Text


class Citation(Reference):
    supports_claim: Text
    quote_or_summary: Literal["verbatim", "summary"] | None = None


class Draft(ToolModel):
    draft_text: Text
    citations: list[Citation]
    is_refusal: Literal[False]
    refusal: None


class PricingEvidence(ToolModel):
    document_id: Text
    source_url: Text
    relevant_passage: Text
    reference: Positive
    estimate_groups: list[Text]


class PriceComponent(ToolModel):
    sku: Text
    label: Text
    quantity: Count
    billing_unit: Text
    free_units: Count
    billable_units: Count


class Estimate(ToolModel):
    scenario: Text
    currency: Literal["USD", "INR"]
    monthly_cost: str | None
    monthly_cost_inr: str | None
    components: Annotated[list[PriceComponent], Field(min_length=1)]
    source_references: Annotated[list[Reference], Field(min_length=1)]
    assumptions: list[Text]


class PricingResult(ToolModel):
    status: Literal["verified", "partial", "missing_evidence"]
    estimates: list[Estimate]
    reason: Text | None


class DocumentResult(ToolModel):
    status: Literal["verified", "missing_evidence"]
    findings: list[Reference]
    reason: Text | None
    summary: Text | None = None


class ProviderResult(ToolModel):
    provider: Provider
    pricing: PricingResult
    limits: DocumentResult
    coverage: DocumentResult


class Comparison(ToolModel):
    applicable: bool
    providers: list[Provider]
    dimensions: list[Dimension]
    assumptions: list[Text]
    source_urls: list[Text]
    equivalent_requirements: Requirements | None = None
    provider_results: list[ProviderResult] | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def align_combined_results(self):
        if self.provider_results is not None:
            if [row.provider for row in self.provider_results] != self.providers:
                raise ValueError("results must match the requested providers")
            if not self.applicable or self.dimensions != ["pricing", "limits", "coverage"]:
                raise ValueError("combined results must include pricing, limits, and coverage")
        return self


class AppComparisonOutput(ToolModel):
    draft: Draft | None
    comparison: Comparison | None
    pricing_source_hits: list[PricingEvidence]

    @model_validator(mode="after")
    def pair_draft_and_comparison(self):
        if (self.draft is None) != (self.comparison is None):
            raise ValueError("a comparison and its draft must be returned together")
        return self


class FieldUpdateInput(ToolModel):
    record_id: Text
    field_name: Text
    previous_value: JsonValue
    proposed_value: JsonValue
    reason: Text


class FieldUpdateAudit(ToolModel):
    created_at: Text
    reviewer: None
    decision: None


class FieldUpdateOutput(ToolModel):
    record_id: Text
    field: Text
    previous_value: JsonValue
    proposed_value: JsonValue
    reason: Text
    status: Literal["pending_human_approval"]
    approval_status: Literal["pending"]
    audit: FieldUpdateAudit


class RecordFields(ToolModel):
    status: Text | None = None
    stage: Text | None = None
    owner: Literal["Support L1", "Support L2", "Account team (Sales)", "Maps engineering"] | None = None
    api: API | None = None
    category: Text | None = None
    providers: Text | None = None
    severity: Literal["SEV1", "SEV2", "SEV3", "SEV4"] | None = None
    next_step: Text | None = None

    @model_validator(mode="after")
    def require_at_least_one_field(self):
        values = self.model_dump(exclude_unset=True)
        if not values or any(value is None for value in values.values()):
            raise ValueError("record proposals require at least one non-null field")
        return self


class RecordUpdateInput(ToolModel):
    record_id: RecordId
    fields: RecordFields


class Change(ToolModel):
    old: JsonValue
    new: JsonValue


class RecordProposal(ToolModel):
    record_id: RecordId
    mode: Literal["propose"]
    fields: RecordFields
    diff: Annotated[dict[str, Change], Field(min_length=1)]


class RecordUpdateOutput(ToolModel):
    proposal: RecordProposal | None



class OpenAIFunction(ToolModel):
    name: Text
    arguments: str


class OpenAIFunctionCall(ToolModel):
    id: Text
    type: Literal["function"]
    function: OpenAIFunction
