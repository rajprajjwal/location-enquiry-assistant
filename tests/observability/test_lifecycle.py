"""Late workers and remote failures must not restore locally deleted traces."""
from decimal import Decimal
from contextlib import closing
import json
from threading import Event
from types import SimpleNamespace

import pytest

from copilot.case_storage.db import connect
from copilot.model_gateway.reliability import Limits, ToolTimeout, bounded_tool, query_session
from copilot.observability import trace_run, observed_span
from copilot.observability import storage, sync_deletions
from copilot.observability.tracing import current_run, set_usage
from copilot.observability.costs import Rates, aggregate_usage


def test_late_worker_does_not_change_sealed_trace(tmp_path):
    release, finished = Event(), Event()
    def work(_):
        try:
            with observed_span("late.worker"):
                release.wait(2)
        finally:
            finished.set()
    with closing(connect(tmp_path / "late.db")) as con:
        with trace_run(connection=con) as capture, query_session(Limits(tool_timeout_seconds=.01)):
            with pytest.raises(ToolTimeout):
                bounded_tool(work, {})
        before = storage.get_run(con, capture.trace_id)
        release.set()
        assert finished.wait(2)
        assert storage.get_run(con, capture.trace_id) == before
        assert current_run() is None and capture.sealed
        worker = next(s for s in before["spans"] if s["name"] == "late.worker")
        assert worker["ended_ns"] is None and worker["status"] == "IN_PROGRESS"


def test_remote_deletion_can_retry_after_local_trace_is_removed(tmp_path, monkeypatch):
    with closing(connect(tmp_path / "delete.db")) as con:
        with trace_run(connection=con) as capture:
            pass
        summary = dict(capture.summary, export_mode="langfuse")
        with con:
            con.execute("UPDATE observability_runs SET summary_json=? WHERE trace_id=?", (json.dumps(summary), capture.trace_id))
            storage.delete_run(con, capture.trace_id)
        assert storage.get_run(con, capture.trace_id) is None
        monkeypatch.setenv("LANGFUSE_BASE_URL", "https://example.invalid")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "example-public")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "example-secret")
        class Client:
            fails = True
            def __init__(self, **kwargs):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def delete(self, path):
                assert path.endswith(capture.trace_id)
                if self.fails:
                    raise TimeoutError("example-secret must not enter the queue")
                return SimpleNamespace(status_code=204, raise_for_status=lambda: None)
        monkeypatch.setattr(sync_deletions.httpx, "Client", Client)
        assert sync_deletions.process_pending_deletions(con) == {"submitted": 0, "failed": 1}
        pending = dict(con.execute("SELECT * FROM observability_trace_deletions").fetchone())
        assert pending["last_error"] == "TimeoutError" and pending["status"] == "pending"
        Client.fails = False
        assert sync_deletions.process_pending_deletions(con) == {"submitted": 1, "failed": 0}
        assert con.execute("SELECT status FROM observability_trace_deletions").fetchone()[0] == "submitted"
        assert storage.get_run(con, capture.trace_id) is None


def test_negative_usage_is_not_exported_or_priced():
    with trace_run() as run:
        with observed_span("llm.request", kind="llm_attempt") as span:
            set_usage(span, {"prompt_tokens": -10, "completion_tokens": 5})
    item = next(s for s in run.spans.values() if s["name"] == "llm.request")
    assert "gen_ai.usage.input_tokens" not in item["attributes"]
    assert "input" not in json.loads(item["attributes"]["langfuse.observation.usage_details"])
    priced = aggregate_usage([item], Rates(input_usd_per_million=1, output_usd_per_million=1))
    assert priced["cost_usd"] is None and priced["missing_usage_attempts"] == 1


def test_illustrative_estimate_keeps_actual_free_access_separate():
    rates = Rates(input_usd_per_million="0.10", output_usd_per_million="0.20",
                  embedding_usd_per_million="0.02", usd_to_inr=94,
                  cost_basis="illustrative", endpoint_access_free=True)
    spans = [{"attributes": {"copilot.span.kind": "llm_attempt", "gen_ai.usage.input_tokens": 1000,
                              "gen_ai.usage.output_tokens": 500}}]
    result = aggregate_usage(spans, rates)
    assert Decimal(result["cost_usd"]) == Decimal("0.00020") and Decimal(result["cost_inr"]) == Decimal("0.01880")
    assert result["actual_endpoint_charge_inr"] == "0" and result["cost_basis"] == "illustrative"
