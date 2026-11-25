"""The same prediction and metric contracts serve both evaluation arms."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str
    span: str
    supports_claim: str


class Prediction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    answer: str
    citations: list[Citation]
    clarifying_questions: list[str]
    qualification: dict[str, Any]
    comparison: dict[str, Any]
    owner: str | None
    next_action: str | None
    should_escalate: bool | None
    record_update: dict[str, Any] | None
    intent: str | None
    api: str | None
    team: str | None


class Judgement(BaseModel):
    model_config = ConfigDict(extra='forbid')
    answer_accuracy: float = Field(ge=0, le=1)
    grounding: float = Field(ge=0, le=1)
    comparison_completeness: float = Field(ge=0, le=1)
    qualification_completeness: float = Field(ge=0, le=1)
    history_use: float = Field(ge=0, le=1)
    citation_supported: list[bool]
    reasons: dict[str, str]


METRICS = {
    'answer_accuracy': ('Rubric answer accuracy', 'ratio', True),
    'grounding': ('Supported factual claims', 'ratio', True),
    'citation_coverage': ('Drafts with verified citations', 'ratio', True),
    'citation_precision': ('Supported citations', 'ratio', True),
    'comparison_completeness': ('Comparison completeness', 'ratio', True),
    'qualification_completeness': ('Qualification completeness (strict fields)', 'ratio', True),
    'history_use': ('History use', 'ratio', True),
    'owner_accuracy': ('Owner correctness', 'ratio', True),
    'next_action_correctness': ('Next-action correctness', 'ratio', True),
    'tool_execution_success': ('Successful registered tool calls', 'ratio', True),
    'expected_tool_coverage': ('Expected tool coverage', 'ratio', True),
    'schema_validity': ('Prediction schema validity', 'ratio', True),
    'draft_yield': ('Nonempty drafts', 'ratio', True),
    **{f'span_recall_at_{k}': (f'Verbatim span Recall@{k}', 'ratio', True) for k in (1,5,10)},
    **{f'source_recall_at_{k}': (f'Source URL Recall@{k}', 'ratio', True) for k in (1,5,10)},
    'span_mrr': ('Verbatim span MRR', 'ratio', True),
    'latency_ms': ('Generation latency', 'ms', False),
    'cost_inr': ('Estimated generation cost', 'INR', False),
    'input_tokens': ('Reported input tokens', 'tokens', False),
    'output_tokens': ('Reported output tokens', 'tokens', False),
    'embedding_tokens': ('Reported embedding tokens', 'tokens', False),
    'judge_latency_ms': ('Evaluation judge latency', 'ms', False),
    'judge_cost_inr': ('Estimated evaluation judge cost', 'INR', False),
    'retrieval_probe_latency_ms': ('Independent retrieval probe latency', 'ms', False),
    'retrieval_probe_cost_inr': ('Estimated retrieval probe cost', 'INR', False),
}
