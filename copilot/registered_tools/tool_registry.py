# Source history: Vinayagam Raja (ca2437d), master. See copilot/enquiry_workflow/source-history.json.
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from pydantic import BaseModel, ValidationError
from copilot.model_gateway.reliability import active_query, query_scope, bounded_tool, ReliabilityError

from copilot.observability.tracing import observed_span

from .tool_contracts import (
    AppComparisonInput, AppComparisonOutput, CalculatorInput, CalculatorOutput,
    FieldUpdateInput, FieldUpdateOutput, OpenAIFunctionCall, RecordUpdateInput, RecordUpdateOutput,
    SearchInput, SearchOutput,
)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    executor: Callable[[Dict[str, Any]], Dict[str, Any]]
    retry_safe: bool = False

    @property
    def input_schema(self) -> dict:
        return self.input_model.model_json_schema()

    @property
    def output_schema(self) -> dict:
        return self.output_model.model_json_schema()

    def as_openai_function(self) -> Dict[str, Any]:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": self.input_schema,
        }}


def _metadata(value):
    # Store shape and counts, without query text, document passages, or record values.
    if not isinstance(value, dict):
        return {"type": type(value).__name__}
    return {"field_count": len(value),
            "collection_sizes": [len(item) for item in value.values() if isinstance(item, (dict, list))]}


class ToolRegistry:
    """Run registered tools and validate both sides of each call."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self.execution_log: List[Dict[str, Any]] = []

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> List[str]:
        return sorted(self._tools)

    def function_specs(self) -> list[dict]:
        return [self._tools[name].as_openai_function() for name in self.list_tools()]

    @query_scope()
    def execute(self, tool_name: str, arguments: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        return self._execute(tool_name, arguments)

    @query_scope()
    def execute_openai_call(self, call: Mapping[str, Any]) -> dict:
        """Dispatch a function call and return the matching OpenAI tool message."""
        payload = OpenAIFunctionCall.model_validate(dict(call))
        result = self._execute(payload.function.name, payload.function.arguments, from_json=True)
        return {"role": "tool", "tool_call_id": payload.id, "content": json.dumps(result, ensure_ascii=False)}

    def _execute(self, tool_name, arguments, *, from_json=False):
        tool = self._tools.get(tool_name)
        name = tool.name if tool else "unregistered"
        with observed_span(f"tool.{name}", kind="tool", attributes={
            "tool.name": name, "langfuse.observation.type": "tool",
        }) as observation:
            try:
                return self._execute_inner(tool_name, arguments, from_json=from_json)
            finally:
                if observation is not None and self.execution_log:
                    entry = self.execution_log[-1]
                    for key in ("input_validation", "output_validation", "execution_status", "attempts"):
                        if key in entry:
                            observation.set_attribute(f"tool.{key}", entry[key])

    def _execute_inner(self, tool_name, arguments, *, from_json=False):
        started_at = time.perf_counter()
        tool = self._tools.get(tool_name)
        entry = {
            "tool_name": tool.name if tool else "<unregistered>",
            "registered": tool is not None,
            "invocation_timestamp": datetime.now(timezone.utc).isoformat(),
            "input_metadata": _metadata(arguments),
            "input_validation": "not_run",
            "output_validation": "not_run",
            "validation_result": "not_run",
            "execution_status": "rejected",
            "output_metadata": None,
            "error_details": None,
        }
        try:
            if tool is None:
                entry["error_details"] = "Unregistered tool"
                raise KeyError("Unregistered tool")
            try:
                if from_json:
                    parsed = tool.input_model.model_validate_json(arguments)
                else:
                    payload = {} if arguments is None else arguments
                    parsed = tool.input_model.model_validate(payload)
            except ValidationError as exc:
                entry.update(input_validation="failed", validation_result="failed", error_details="Invalid input")
                raise ValueError(f"Input validation failed for {tool.name}") from exc
            entry.update(input_validation="passed", input_metadata=_metadata(parsed.model_dump(exclude_unset=True)))
            try:
                session = active_query()
                entry["attempts"] = 0
                retry_limit = session.limits.max_retries_per_step if tool.retry_safe else 0
                for attempt in range(retry_limit + 1):
                    if attempt:
                        session.retry()
                    entry["attempts"] += 1
                    try:
                        result = bounded_tool(tool.executor, parsed.model_dump(mode="json", exclude_unset=True))
                        break
                    except ReliabilityError:
                        if attempt == retry_limit:
                            raise
                    except (RuntimeError, TimeoutError):
                        session.event("tool_error", tool=tool.name)
                        if attempt == retry_limit:
                            raise
            except Exception as exc:
                entry.update(execution_status="error", error_details=type(exc).__name__)
                raise RuntimeError(f"Tool execution failed for {tool.name}") from exc
            try:
                output = tool.output_model.model_validate(result).model_dump(mode="json", exclude_unset=True)
            except ValidationError as exc:
                entry.update(output_validation="failed", validation_result="failed",
                             execution_status="error", error_details="Invalid output")
                raise ValueError(f"Output validation failed for {tool.name}") from exc
            entry.update(output_validation="passed", validation_result="passed",
                         execution_status="success", output_metadata=_metadata(output))
            return output
        finally:
            entry["execution_duration_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
            self.execution_log.append(entry)


class DocumentSearchTool:
    """Adapter for the C4 document retrieval component.

    This is intentionally thin and integration-friendly: the implementation accepts a
    search function or a static corpus so the actual C4 retrieval system can be
    connected without duplicating the full ingestion pipeline.
    """

    def __init__(self, documents: Optional[Sequence[Mapping[str, Any]]] = None, search_function: Optional[Callable[[str], Sequence[Mapping[str, Any]]]] = None, *, scoped_search=None):
        self.documents = list(documents or [])
        self.search_function = search_function
        self.scoped_search = scoped_search

    def search(self, query: str, *, max_results: int = 5, scope=None) -> List[Dict[str, Any]]:
        if scope and self.scoped_search is not None:
            results = list(self.scoped_search(scope))
        elif self.search_function is not None:
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
            retry_safe=True,
            description="Search approved location-services documentation and return ranked, evidence-backed results.",
            input_model=SearchInput,
            output_model=SearchOutput,
            executor=lambda arguments: {"results": self.search(
                arguments["query"], max_results=arguments.get("max_results", 5), scope=arguments.get("scope"),
            )},
        )


class ComparisonTool:
    """Typed wrapper for the deterministic comparison engine."""

    def __init__(self, comparison_function, *, app=False):
        self.comparison_function = comparison_function
        self.app = app

    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="compare_providers",
            retry_safe=True,
            description="Compare provider pricing, limits and coverage using equivalent requirements.",
            input_model=AppComparisonInput if self.app else CalculatorInput,
            output_model=AppComparisonOutput if self.app else CalculatorOutput,
            executor=self.comparison_function,
        )


class SandboxRecordUpdateTool:
    """Lightweight sandbox proposal tool for record changes.

    The tool never writes to production systems. It stores the proposal in a mock
    record and marks it as pending human approval.
    """

    def __init__(self, sandbox_store: Optional[Dict[str, Any]] = None, *, proposal_function=None):
        self.sandbox_store = sandbox_store if sandbox_store is not None else {}
        self.proposal_function = proposal_function

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
            retry_safe=self.proposal_function is not None,
            description="Propose field-level updates in the sandbox-only record store and require human approval.",
            input_model=RecordUpdateInput if self.proposal_function is not None else FieldUpdateInput,
            output_model=RecordUpdateOutput if self.proposal_function is not None else FieldUpdateOutput,
            executor=self.proposal_function or (lambda arguments: self.propose_change(
                arguments["record_id"],
                arguments["field_name"],
                arguments["previous_value"],
                arguments["proposed_value"],
                arguments["reason"],
            )),
        )
