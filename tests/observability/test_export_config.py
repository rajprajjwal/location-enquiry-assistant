"""Langfuse exporter configuration: base URL normalisation and export status."""
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExportResult

from copilot.observability import exporters


def test_dashboard_link_is_reduced_to_the_api_host():
    assert exporters.langfuse_base_url("https://us.cloud.langfuse.com/project/abc123/traces") == "https://us.cloud.langfuse.com"
    assert exporters.langfuse_base_url("https://us.cloud.langfuse.com/") == "https://us.cloud.langfuse.com"
    assert exporters.langfuse_base_url("https://traces.example.com/api/public/otel") == "https://traces.example.com"
    assert exporters.langfuse_base_url("http://localhost:3000") == "http://localhost:3000"


def test_configured_endpoint_ignores_a_pasted_dashboard_path(monkeypatch):
    monkeypatch.setenv("COPILOT_TRACE_EXPORT", "langfuse")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com/project/abc123/traces")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setattr(exporters, "EXPORT_STATUS", dict(exporters.EXPORT_STATUS, note=None, error=None))
    exporters.configure_remote(TracerProvider())
    assert exporters.EXPORT_STATUS["endpoint"] == "https://us.cloud.langfuse.com/api/public/otel/v1/traces"
    assert "dashboard path" in exporters.EXPORT_STATUS["note"]


def test_missing_key_is_reported_instead_of_silent(monkeypatch):
    monkeypatch.setenv("COPILOT_TRACE_EXPORT", "langfuse")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.setattr(exporters, "EXPORT_STATUS", dict(exporters.EXPORT_STATUS, error=None, endpoint=None))
    exporters.configure_remote(TracerProvider())
    assert "LANGFUSE_PUBLIC_KEY" in exporters.EXPORT_STATUS["error"]


def test_failed_exports_are_recorded(monkeypatch):
    class Failing:
        def export(self, spans):
            return SpanExportResult.FAILURE

    monkeypatch.setattr(exporters, "EXPORT_STATUS", dict(exporters.EXPORT_STATUS, exported_spans=0, last_result=None))
    exporters._RecordingExporter(Failing()).export([object()])
    assert exporters.EXPORT_STATUS["last_result"] == "FAILURE"
    assert exporters.EXPORT_STATUS["exported_spans"] == 0
