"""Lightweight deterministic support modules for the Location Services Sales and Support Copilot.

This package contains the comparison/calculation engine, the typed tool registry and
conversation-state management needed for the in-scope capstone workflow.
"""

from .comparison_engine import (
    CapabilityComparison,
    CoverageStatus,
    LimitComparison,
    PricePlan,
    PriceTier,
    compare_capabilities,
    compare_coverage,
    compare_limits,
    compare_provider_pricing,
    deterministic_cost_estimate,
    normalize_billing_unit,
)
from .conversation_state import ConversationState
from .tool_registry import (
    ComparisonTool,
    DocumentSearchTool,
    SandboxRecordUpdateTool,
    ToolDefinition,
    ToolRegistry,
)

__all__ = [
    "CapabilityComparison",
    "ComparisonTool",
    "ConversationState",
    "CoverageStatus",
    "DocumentSearchTool",
    "LimitComparison",
    "PricePlan",
    "PriceTier",
    "SandboxRecordUpdateTool",
    "ToolDefinition",
    "ToolRegistry",
    "compare_capabilities",
    "compare_coverage",
    "compare_limits",
    "compare_provider_pricing",
    "deterministic_cost_estimate",
    "normalize_billing_unit",
]
