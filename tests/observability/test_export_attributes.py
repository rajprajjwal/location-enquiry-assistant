"""Langfuse export: trace-wide attributes on every span, content kept out of the local store."""
from contextlib import closing
import json

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from copilot.case_storage.db import connect
from copilot.observability import storage, tracing
from copilot.observability.exporters import RunExportProcessor, trace_environment
from copilot.observability.tracing import observed_span, record_trace_io, set_io, trace_run


def _provider(monkeypatch):
    exported = InMemorySpanExporter()
    instance = TracerProvider(resource=Resource.create({"service.name": "test"}))
    instance.add_span_processor(tracing._LocalProcessor())
    instance.add_span_processor(RunExportProcessor(SimpleSpanProcessor(exported)))
    monkeypatch.setattr(tracing, "provider", lambda: instance)
    return exported


def test_every_exported_span_carries_session_environment_and_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_TRACE_ENVIRONMENT", "production")
    exported = _provider(monkeypatch)
    with closing(connect(tmp_path / "export.db")) as con:
        with trace_run(connection=con, metadata={"bucket": "docs"}) as run:
            with observed_span("workflow.draft", kind="workflow_step"):
                with observed_span("generate-draft", kind="llm_attempt") as generation:
                    set_io(generation, input=[{"role": "user", "content": "redacted question"}],
                           output={"role": "assistant", "content": "cited answer"})
            record_trace_io(input="redacted question", output="customer reply")
            # The case ID is only known after the workflow, as for a new case in run_case.
            run.tag(case_id="case-123", api="directions", team="Support")
    spans = exported.get_finished_spans()
    assert len(spans) == 3
    for span in spans:
        assert span.attributes["langfuse.session.id"] == "case-123"
        assert span.attributes["langfuse.environment"] == "production"
        assert span.attributes["langfuse.trace.name"] == "enquiry"
        assert span.attributes["langfuse.trace.metadata.api"] == "directions"
        assert span.attributes["langfuse.trace.metadata.bucket"] == "docs"
        assert "langfuse.trace.metadata" not in span.attributes
    root = next(span for span in spans if span.parent is None)
    assert root.attributes["langfuse.observation.input"] == "redacted question"
    assert root.attributes["langfuse.observation.output"] == "customer reply"
    generation = next(span for span in spans if span.name == "generate-draft")
    assert json.loads(generation.attributes["langfuse.observation.output"])["content"] == "cited answer"


def test_local_trace_store_keeps_no_prompt_or_reply_text(tmp_path, monkeypatch):
    _provider(monkeypatch)
    with closing(connect(tmp_path / "local.db")) as con:
        with trace_run(connection=con) as run:
            with observed_span("generate-draft", kind="llm_attempt") as generation:
                set_io(generation, input="private prompt text", output="private reply text")
            record_trace_io(input="private question", output="private answer")
        saved = json.dumps(storage.get_run(con, run.trace_id))
    for text in ("private prompt text", "private reply text", "private question", "private answer"):
        assert text not in saved


def test_content_capture_can_be_disabled(monkeypatch):
    exported = _provider(monkeypatch)
    monkeypatch.setenv("COPILOT_TRACE_CAPTURE_CONTENT", "0")
    with trace_run():
        with observed_span("generate-draft", kind="llm_attempt") as generation:
            set_io(generation, input="prompt", output="reply")
    assert all("langfuse.observation.input" not in span.attributes for span in exported.get_finished_spans())


def test_invalid_environment_falls_back_to_development(monkeypatch):
    monkeypatch.setenv("COPILOT_TRACE_ENVIRONMENT", "Langfuse Prod!")
    assert trace_environment() == "development"
