"""Optional OTLP/HTTP export; local tracing does not need an external service."""
import base64
import json
import logging
import os
import re
from urllib.parse import urlsplit

from datetime import datetime, timezone

from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult


_LOG = logging.getLogger(__name__)
_ENVIRONMENT = re.compile(r"^(?!langfuse)[a-z0-9_-]{1,40}$")
# Trace-wide run metadata copied to every exported span as filterable Langfuse metadata.
_TRACE_METADATA = ("bucket", "api", "team", "split", "run_id", "record_id", "status", "step_count")


def trace_environment():
    """Langfuse environment for exported traces (COPILOT_TRACE_ENVIRONMENT, default development)."""
    value = os.environ.get("COPILOT_TRACE_ENVIRONMENT", "development").strip().lower()
    return value if _ENVIRONMENT.fullmatch(value) else "development"


def trace_attributes(run, root):
    """Attributes Langfuse v4 needs on every observation to filter and group one enquiry."""
    attributes = {"langfuse.trace.name": root.name, "langfuse.environment": trace_environment()}
    if run.metadata.get("case_id"):
        # One case is one customer conversation: each turn is a trace, the case is the session.
        attributes["langfuse.session.id"] = str(run.metadata["case_id"])
    for key in _TRACE_METADATA:
        if run.metadata.get(key) is not None:
            attributes[f"langfuse.trace.metadata.{key}"] = str(run.metadata[key])
    tags = (root.attributes or {}).get("langfuse.trace.tags")
    if tags:
        attributes["langfuse.trace.tags"] = tuple(tags)
    return attributes


def _root_summary(root):
    # The local JSON summary becomes filterable root metadata instead of one opaque string.
    try:
        summary = json.loads((root.attributes or {}).get("langfuse.trace.metadata") or "{}")
    except ValueError:
        return {}
    return {f"langfuse.observation.metadata.{key}": str(value) for key, value in summary.items()
            if key not in _TRACE_METADATA and key != "case_id" and value is not None
            and not isinstance(value, (dict, list))}


def _with_attributes(span, extra):
    attributes = {key: value for key, value in (span.attributes or {}).items() if key != "langfuse.trace.metadata"}
    attributes.update(extra)
    return ReadableSpan(
        name=span.name, context=span.get_span_context(), parent=span.parent, resource=span.resource,
        attributes=attributes, events=span.events, links=span.links, kind=span.kind, status=span.status,
        start_time=span.start_time, end_time=span.end_time, instrumentation_scope=span.instrumentation_scope,
    )


class RunExportProcessor(SpanProcessor):
    """Export each enquiry's spans once, after its root ends, with trace-wide attributes on every span."""

    def __init__(self, downstream):
        self._downstream = downstream

    def on_start(self, span, parent_context=None):
        pass

    def on_end(self, span):
        from .tracing import current_run
        run = current_run()
        if run is None or run.sealed or (run.closing and span.parent is not None):
            return
        with run.lock:
            run.export_buffer.append(span)
            if span.parent is not None:
                return
            spans, run.export_buffer = run.export_buffer, []
        shared = trace_attributes(run, span)
        for item in spans:
            extra = {**shared, **(_root_summary(item) if item.parent is None else {})}
            self._downstream.on_end(_with_attributes(item, extra))

    def shutdown(self):
        self._downstream.shutdown()

    def force_flush(self, timeout_millis=30000):
        return self._downstream.force_flush(timeout_millis)


# Remote export state, shown in the app so a misconfigured exporter is not silent.
EXPORT_STATUS = {"mode": "local", "endpoint": None, "error": None, "note": None,
                 "last_export_utc": None, "last_result": None, "exported_spans": 0}


def langfuse_base_url(value):
    """API host for a Langfuse base URL. A pasted dashboard link (``.../project/<id>/traces``) is reduced to its host."""
    base = value.strip().rstrip("/")
    for marker in ("/project/", "/api/public"):
        if marker in base:
            base = base.split(marker)[0]
    return base


class _RecordingExporter(SpanExporter):
    """Delegates to the OTLP exporter and records each export's outcome in EXPORT_STATUS."""

    def __init__(self, inner):
        self._inner = inner

    def export(self, spans):
        result = self._inner.export(spans)
        EXPORT_STATUS.update(last_export_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             last_result=result.name)
        if result == SpanExportResult.SUCCESS:
            EXPORT_STATUS["exported_spans"] += len(spans)
        return result

    def shutdown(self):
        self._inner.shutdown()

    def force_flush(self, timeout_millis=30000):
        return self._inner.force_flush(timeout_millis)


def check_langfuse_access(base, public_key, secret_key):
    """One authenticated read against the project. Returns (ok, message) without exposing keys."""
    import httpx

    try:
        response = httpx.get(f"{base}/api/public/projects", timeout=15, auth=(public_key, secret_key))
    except Exception as error:
        return False, f"cannot reach {base} ({type(error).__name__})"
    if response.status_code == 200:
        projects = response.json().get("data") or [{}]
        return True, f"connected to project '{projects[0].get('name', '?')}'"
    if response.status_code == 401:
        return False, ("keys rejected (HTTP 401): the keys belong to another region or project. "
                       "EU is https://cloud.langfuse.com, US is https://us.cloud.langfuse.com")
    return False, f"HTTP {response.status_code} from {base}: LANGFUSE_BASE_URL must be the API host, e.g. https://us.cloud.langfuse.com"


def configure_remote(provider):
    mode = os.environ.get("COPILOT_TRACE_EXPORT", "local")
    EXPORT_STATUS["mode"] = mode
    if mode == "local":
        return
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        if mode in {"langfuse", "langfuse-local"}:
            if mode == "langfuse-local":
                from .langfuse_local import load_environment
                values = load_environment()
            else:
                values = os.environ
            base = langfuse_base_url(values["LANGFUSE_BASE_URL"])
            if base != values["LANGFUSE_BASE_URL"].strip().rstrip("/"):
                EXPORT_STATUS["note"] = f"LANGFUSE_BASE_URL contained a dashboard path; using {base}"
            endpoint = base + "/api/public/otel/v1/traces"
            credentials = values["LANGFUSE_PUBLIC_KEY"] + ":" + values["LANGFUSE_SECRET_KEY"]
            headers = {"Authorization": "Basic " + base64.b64encode(credentials.encode()).decode(),
                       "x-langfuse-ingestion-version": "4"}
        elif mode == "otlp":
            endpoint = os.environ["COPILOT_OTLP_TRACES_ENDPOINT"]
            headers = {}
        else:
            raise ValueError("Unknown trace export mode")
        address = urlsplit(endpoint)
        if address.scheme != "https" and not (address.scheme == "http" and address.hostname in {"127.0.0.1", "localhost"}):
            raise ValueError("Trace endpoint requires HTTPS or localhost")
        if address.username or address.password or address.query:
            raise ValueError("Keep trace credentials in headers")
        exporter = _RecordingExporter(OTLPSpanExporter(endpoint=endpoint, headers=headers, timeout=30))
        provider.add_span_processor(RunExportProcessor(BatchSpanProcessor(exporter, schedule_delay_millis=1000)))
        EXPORT_STATUS["endpoint"] = endpoint
    except Exception as error:
        EXPORT_STATUS["error"] = f"{type(error).__name__}: {error}" if isinstance(error, KeyError) else type(error).__name__
        _LOG.warning("Remote tracing unavailable (%s); local spans remain enabled", type(error).__name__)
