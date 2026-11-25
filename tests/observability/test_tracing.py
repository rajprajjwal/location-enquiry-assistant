"""Trace completeness, accounting, privacy and route invariance."""
from contextlib import closing
from decimal import Decimal
import json

import pytest

from copilot.case_storage.db import connect
from copilot.enquiry_workflow.cases import run_case
from copilot.enquiry_workflow.deletion import delete_enquiry
from copilot.enquiry_workflow.verification.reliability_faults import Clock, FaultClient
from copilot.model_gateway.reliability import query_session
from copilot.observability import trace_run, observed_span
from copilot.observability import costs, storage
from copilot.observability.costs import Rates, aggregate_usage
from copilot.observability.tracing import set_usage
from copilot.registered_tools.tool_registry import DocumentSearchTool, ToolRegistry


@pytest.fixture
def rates(monkeypatch):
    value = Rates(input_usd_per_million=2, output_usd_per_million=4,
                  embedding_usd_per_million=1, usd_to_inr=94, source="Unit-test fixture rates")
    monkeypatch.setattr(costs, "configured_rates", lambda: value)
    return value


def attempt(incoming=None, outgoing=None, kind="llm_attempt"):
    attrs = {"copilot.span.kind": kind}
    if incoming is not None:
        attrs["gen_ai.usage.input_tokens"] = incoming
    if outgoing is not None:
        attrs["gen_ai.usage.output_tokens"] = outgoing
    return {"attributes": attrs}


def test_hand_calculated_cost_and_fx_without_counting_parent_spans(rates):
    rows = [attempt(1000, 500), attempt(200, kind="embedding_attempt"),
            {"attributes": {"copilot.span.kind": "phase", "gen_ai.usage.input_tokens": 99999}}]
    result = aggregate_usage(rows, rates)
    assert Decimal(result["cost_usd"]) == Decimal("0.0042")
    assert Decimal(result["cost_inr"]) == Decimal("0.3948")
    assert result["model_attempts"] == 1 and result["embedding_attempts"] == 1
    assert result["input_tokens"] == 1000 and result["embedding_tokens"] == 200


def test_unknown_rates_and_missing_usage_are_not_reported_as_zero_cost(rates):
    assert aggregate_usage([attempt(10, 5)], Rates())["cost_usd"] is None
    partial = aggregate_usage([attempt(1000, 500), attempt()], rates)
    assert partial["cost_status"] == "incomplete_usage"
    assert partial["cost_usd"] is None and partial["missing_usage_attempts"] == 1
    assert Decimal(partial["known_cost_usd"]) == Decimal("0.004")


def test_explicit_free_access_remains_distinct_from_unknown_usage():
    free = aggregate_usage([attempt()], Rates(input_usd_per_million=0, output_usd_per_million=0))
    assert free["cost_usd"] == "0" and not free["usage_complete"]


def test_nested_trace_and_worker_span_keep_parent_ids(tmp_path, rates):
    def search(query):
        with observed_span("retrieval.documents", kind="retrieval"):
            return [{"source_url": "https://example.test/docs", "relevant_passage": "API documentation."}]
    registry = ToolRegistry()
    registry.register(DocumentSearchTool(search_function=search).tool_definition())
    with closing(connect(tmp_path / "trace.db")) as con:
        with trace_run(connection=con, metadata={"bucket": "docs", "split": "synthetic"}) as run:
            with observed_span("workflow.document_search", kind="workflow_step"):
                registry.execute(registry.list_tools()[0], {"query": "Directions API"})
        stored = storage.get_run(con, run.trace_id)
        worker = next(s for s in stored["spans"] if s["name"] == "retrieval.documents")
        tool = next(s for s in stored["spans"] if s["kind"] == "tool")
        assert worker["parent_span_id"] == tool["span_id"]
        assert all(s["ended_ns"] is not None for s in stored["spans"])
        assert {s["trace_id"] for s in stored["spans"]} == {run.trace_id}
        assert storage.list_runs(con, bucket="ownership") == []
        assert len(storage.list_runs(con, bucket="docs", min_latency_ms=0)) == 1


def test_physical_retries_are_counted_once_and_missing_usage_remains_visible(tmp_path, rates):
    clock = Clock()
    client = FaultClient("transient_model_timeout", clock)
    with closing(connect(tmp_path / "retry.db")) as con:
        with trace_run(connection=con) as run, query_session(clock=clock, sleeper=clock.advance):
            client.complete([{"role": "user", "content": "Explain Directions"}], max_tokens=512)
        stored = storage.get_run(con, run.trace_id)
        attempts = [s for s in stored["spans"] if s["kind"] == "llm_attempt"]
        assert len(attempts) == client.calls == stored["model_attempts"] == 2
        assert [s["status"] for s in attempts] == ["ERROR", "OK"]
        assert stored["missing_usage_attempts"] == 1
        assert stored["cost_usd"] is None


def test_exception_contents_do_not_enter_spans(tmp_path, rates):
    secret = "api_key=private-test-secret-do-not-export"
    with closing(connect(tmp_path / "private.db")) as con:
        with pytest.raises(ValueError), trace_run(connection=con) as run:
            with observed_span("test.failure"):
                raise ValueError(secret)
        assert secret not in json.dumps(storage.get_run(con, run.trace_id))
        assert storage.get_run(con, run.trace_id)["outcome"] == "error"


def business_projection(result):
    keys = ("status", "outputs", "clarifying_questions", "proposed_actions", "critic")
    return {key: result[key] for key in keys}


def test_case_instrumentation_keeps_routes_questions_and_pending_state(tmp_path, monkeypatch, rates):
    results = []
    for enabled in ("0", "1"):
        monkeypatch.setenv("COPILOT_TRACING_ENABLED", enabled)
        clock = Clock()
        with closing(connect(tmp_path / f"case-{enabled}.db")) as con:
            with query_session(clock=clock, sleeper=clock.advance):
                result = run_case(con, "How do I set waypoints in the Directions API?",
                                  client=FaultClient("healthy", clock), search=DocumentSearchTool(documents=[]))
            results.append(business_projection(result))
            if enabled == "1":
                saved = storage.get_run(con, result["trace_id"])
                assert saved and saved["model_attempts"] > 0
                assert {"interpretation", "follow_up_planning", "output_validation"}.issubset(
                    {s["name"] for s in saved["spans"]})
                assert len([s for s in saved["spans"] if s["kind"] == "workflow_step"]) == result["step_count"]
                delete_enquiry(con, result["trace_id"])
                assert storage.get_run(con, result["trace_id"]) is None
    assert results[0] == results[1]


def test_persistence_failure_does_not_change_enquiry_result(tmp_path, monkeypatch, caplog):
    def unavailable(*args):
        raise OSError("private-store-details")
    monkeypatch.setattr(storage, "save_run", unavailable)
    with closing(connect(tmp_path / "failure.db")) as con:
        clock = Clock()
        with query_session(clock=clock, sleeper=clock.advance):
            result = run_case(con, "How do I set waypoints in the Directions API?",
                              client=FaultClient("healthy", clock), search=DocumentSearchTool(documents=[]))
        assert result["status"] == "clarification_needed"
    assert "private-store-details" not in caplog.text
