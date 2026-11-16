from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

from jsonschema import Draft202012Validator


def _redact_sensitive_fields(value: Any, path: str = "") -> Any:
    if isinstance(value, dict):
        redacted: Dict[str, Any] = {}
        for key, nested in value.items():
            if re.search(r"(api[_-]?key|token|secret|password|credential|customer|pii)", str(key).lower()):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_sensitive_fields(nested, f"{path}.{key}")
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive_fields(item, path) for item in value]
    return value


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    executor: Callable[[Dict[str, Any]], Dict[str, Any]]

    def as_openai_function(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class ToolRegistry:
    """Registry for typed tools used in the capstone flow.

    This registry intentionally accepts only explicit tool names and typed schemas.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self.execution_log: List[Dict[str, Any]] = []

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> List[str]:
        return sorted(self._tools.keys())

    def execute(self, tool_name: str, arguments: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        if tool_name not in self._tools:
            raise KeyError(f"Unregistered tool: {tool_name}")

        tool = self._tools[tool_name]
        payload = dict(arguments or {})
        validator = Draft202012Validator(tool.input_schema)
        validation_errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
        if validation_errors:
            first_error = validation_errors[0]
            raise ValueError(f"Input validation failed for {tool_name}: {first_error.message}")

        started_at = time.perf_counter()
        try:
            result = tool.executor(payload)
            status = "success"
            error = None
        except Exception as exc:  # pragma: no cover - runtime error path exercised in tests
            result = {"status": "error", "error": str(exc)}
            status = "error"
            error = str(exc)

        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_entry = {
            "tool_name": tool_name,
            "invocation_timestamp": datetime.now(timezone.utc).isoformat(),
            "input_metadata": _redact_sensitive_fields(payload),
            "validation_result": "passed",
            "execution_status": status,
            "output_metadata": _redact_sensitive_fields(result),
            "execution_duration_ms": elapsed_ms,
            "error_details": error,
        }
        self.execution_log.append(log_entry)

        if status == "error":
            raise RuntimeError(f"Tool execution failed for {tool_name}: {error}")

        return result


class DocumentSearchTool:
    """Adapter for the C4 document retrieval component.

    This is intentionally thin and integration-friendly: the implementation accepts a
    search function or a static corpus so the actual C4 retrieval system can be
    connected without duplicating the full ingestion pipeline.
    """

    def __init__(self, documents: Optional[Sequence[Mapping[str, Any]]] = None, search_function: Optional[Callable[[str], Sequence[Mapping[str, Any]]]] = None):
        self.documents = list(documents or [])
        self.search_function = search_function

    def search(self, query: str, *, max_results: int = 5) -> List[Dict[str, Any]]:
        if self.search_function is not None:
            results = list(self.search_function(query))
        else:
            lower_query = query.lower()
            results = []
            for doc in self.documents:
                content = str(doc.get("content", "") + " " + str(doc.get("relevant_passage", ""))).lower()
                score = 1.0 if lower_query in content else 0.0
                if score > 0:
                    item = dict(doc)
                    item["relevance_score"] = score
                    results.append(item)

        ranked = sorted(results, key=lambda row: float(row.get("relevance_score", 0.0)), reverse=True)[:max_results]
        output = []
        for entry in ranked:
            output.append({
                "document_id": entry.get("document_id", "doc-unknown"),
                "document_title": entry.get("document_title", "Unknown document"),
                "source_url": entry.get("source_url", ""),
                "retrieved_date": entry.get("retrieved_date", datetime.now(timezone.utc).date().isoformat()),
                "relevant_passage": entry.get("relevant_passage", entry.get("content", "")),
                "relevance_score": float(entry.get("relevance_score", 0.0)),
                "document_type": entry.get("document_type", "reference"),
            })
        return output

    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="document_search",
            description="Search approved location-services documentation and return ranked, evidence-backed results.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "properties": {
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "document_id": {"type": "string"},
                                "document_title": {"type": "string"},
                                "source_url": {"type": "string"},
                                "retrieved_date": {"type": "string"},
                                "relevant_passage": {"type": "string"},
                                "relevance_score": {"type": "number"},
                                "document_type": {"type": "string"},
                            },
                            "required": ["document_id", "document_title", "source_url", "retrieved_date", "relevant_passage", "relevance_score", "document_type"],
                        },
                    },
                },
            },
            executor=lambda arguments: {"results": self.search(arguments["query"], max_results=arguments.get("max_results", 5))},
        )


class ComparisonTool:
    """Typed wrapper for the deterministic comparison engine."""

    def __init__(self, comparison_function):
        self.comparison_function = comparison_function

    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="compare_providers",
            description="Run deterministic pricing, capability, coverage and limit comparisons for supported location APIs.",
            input_schema={
                "type": "object",
                "properties": {
                    "api": {"type": "string", "enum": ["directions", "distance_matrix", "autocomplete", "reverse_geocode"]},
                    "region": {"type": "string"},
                    "monthly_usage": {"type": "number"},
                    "provider_plans": {"type": "object"},
                    "capability_matrix": {"type": "object"},
                    "coverage_map": {"type": "object"},
                    "limits_map": {"type": "object"},
                    "assumptions": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["api", "monthly_usage", "provider_plans"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "properties": {
                    "comparison_id": {"type": "string"},
                    "requested_api": {"type": "string"},
                    "providers": {"type": "array", "items": {"type": "string"}},
                    "monthly_usage": {"type": "number"},
                    "calculated_costs": {"type": "object"},
                    "pricing_details": {"type": "object"},
                    "capability_differences": {"type": "object"},
                    "coverage_differences": {"type": "object"},
                    "limit_differences": {"type": "object"},
                },
            },
            executor=lambda arguments: self.comparison_function(arguments),
        )


class SandboxRecordUpdateTool:
    """Lightweight sandbox proposal tool for record changes.

    The tool never writes to production systems. It stores the proposal in a mock
    record and marks it as pending human approval.
    """

    def __init__(self, sandbox_store: Optional[Dict[str, Any]] = None):
        self.sandbox_store = sandbox_store if sandbox_store is not None else {}

    def propose_change(self, record_id: str, field_name: str, previous_value: Any, proposed_value: Any, reason: str) -> Dict[str, Any]:
        proposal = {
            "record_id": record_id,
            "field": field_name,
            "previous_value": previous_value,
            "proposed_value": proposed_value,
            "reason": reason,
            "status": "pending_human_approval",
            "approval_status": "pending",
            "audit": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "reviewer": None,
                "decision": None,
            },
        }
        self.sandbox_store.setdefault(record_id, {})[field_name] = proposal
        return proposal

    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="sandbox_record_update",
            description="Propose field-level updates in the sandbox-only record store and require human approval.",
            input_schema={
                "type": "object",
                "properties": {
                    "record_id": {"type": "string"},
                    "field_name": {"type": "string"},
                    "previous_value": {},
                    "proposed_value": {},
                    "reason": {"type": "string"},
                },
                "required": ["record_id", "field_name", "previous_value", "proposed_value", "reason"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "properties": {
                    "record_id": {"type": "string"},
                    "field": {"type": "string"},
                    "previous_value": {},
                    "proposed_value": {},
                    "reason": {"type": "string"},
                    "status": {"type": "string"},
                    "approval_status": {"type": "string"},
                },
            },
            executor=lambda arguments: self.propose_change(
                arguments["record_id"],
                arguments["field_name"],
                arguments["previous_value"],
                arguments["proposed_value"],
                arguments["reason"],
            ),
        )
