"""OpenTelemetry spans captured per enquiry, including context copied to tool workers."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import lru_cache, wraps
from threading import Lock
import json
import logging
import os

from opentelemetry.context import Context
from opentelemetry.trace import Status, StatusCode
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.sampling import ALWAYS_ON


_LOG = logging.getLogger(__name__)
_CURRENT = ContextVar("copilot_trace_run", default=None)
BUCKETS = ("qualification", "interpretation", "docs", "history", "updates", "pricecompare",
           "capabilitycompare", "coveragecompare", "limitscompare", "ownership")
_ALLOWED_METADATA = {"record_id", "run_id", "bucket", "api", "team", "split", "case_id", "status", "step_count"}


@dataclass
class RunTrace:
    metadata: dict = field(default_factory=dict)
    spans: dict = field(default_factory=dict)
    lock: object = field(default_factory=Lock)
    trace_id: str | None = None
    root: object = None
    sealed: bool = False
    closing: bool = False
    summary: dict = field(default_factory=dict)

    def tag(self, **metadata):
        values = {k: v for k, v in metadata.items() if k in _ALLOWED_METADATA and v is not None}
        if values.get("bucket") not in (*BUCKETS, None):
            raise ValueError("Unknown evaluation bucket")
        self.metadata.update(values)
        if self.root:
            for key, value in values.items():
                self.root.set_attribute(f"copilot.{key}", value)
            self.root.set_attribute("langfuse.trace.metadata", json.dumps(self.metadata, sort_keys=True))


def current_run():
    return _CURRENT.get()


def _row(span, *, ended):
    context = span.get_span_context()
    return {
        "trace_id": f"{context.trace_id:032x}", "span_id": f"{context.span_id:016x}",
        "parent_span_id": f"{span.parent.span_id:016x}" if span.parent else None,
        "name": span.name, "start_ns": span.start_time, "end_ns": span.end_time if ended else None,
        "latency_ms": round((span.end_time - span.start_time) / 1_000_000, 3) if ended else None,
        "status": span.status.status_code.name if ended else "IN_PROGRESS",
        "attributes": dict(span.attributes or {}),
    }


class _LocalProcessor(SpanProcessor):
    def on_start(self, span, parent_context=None):
        run = current_run()
        if run is not None:
            with run.lock:
                if not run.sealed and not run.closing:
                    row = _row(span, ended=False)
                    run.spans[row["span_id"]] = row

    def on_end(self, span):
        run = current_run()
        if run is not None:
            with run.lock:
                if not run.sealed and (not run.closing or span.parent is None):
                    row = _row(span, ended=True)
                    run.spans[row["span_id"]] = row

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        return True


@lru_cache(maxsize=1)
def provider():
    instance = TracerProvider(sampler=ALWAYS_ON, resource=Resource.create({"service.name": "location-enquiry-assistant"}))
    instance.add_span_processor(_LocalProcessor())
    from .exporters import configure_remote
    configure_remote(instance)
    return instance


@contextmanager
def observed_span(name, *, kind="phase", attributes=None):
    if current_run() is None:
        yield None
        return
    attrs = {"copilot.span.kind": kind, **(attributes or {})}
    with provider().get_tracer("copilot.observability").start_as_current_span(
        name, attributes=attrs, record_exception=False, set_status_on_exception=False,
    ) as span:
        try:
            yield span
        except BaseException as error:
            span.set_attribute("error.type", type(error).__name__)
            span.set_status(Status(StatusCode.ERROR, type(error).__name__))
            raise
        else:
            if span.status.status_code == StatusCode.UNSET:
                span.set_status(Status(StatusCode.OK))


def tag_run(**metadata):
    if run := current_run():
        run.tag(**metadata)


def set_usage(span, usage, *, embedding=False):
    if span is None:
        return
    usage = usage or {}
    for field, name in (("prompt_tokens", "input_tokens"), ("completion_tokens", "output_tokens")):
        value = usage.get(field)
        if embedding and field == "completion_tokens":
            continue
        if type(value) is int and value >= 0:
            span.set_attribute(f"gen_ai.usage.{name}", value)
    details = {"input": usage["prompt_tokens"]} if type(usage.get("prompt_tokens")) is int and usage["prompt_tokens"] >= 0 else {}
    if not embedding and type(usage.get("completion_tokens")) is int and usage["completion_tokens"] >= 0:
        details["output"] = usage["completion_tokens"]
    if details:
        span.set_attribute("langfuse.observation.usage_details", json.dumps(details))
    try:
        from .costs import aggregate_usage
        priced = aggregate_usage([{"attributes": dict(span.attributes)}])
        span.set_attribute("copilot.cost_status", priced["cost_status"])
        if priced["cost_usd"] is not None:
            span.set_attribute("langfuse.observation.cost_details", json.dumps({"total": float(priced["cost_usd"])}))
            span.set_attribute("copilot.cost_inr", float(priced["cost_inr"]))
    except Exception as error:
        _LOG.warning("Trace usage pricing unavailable (%s)", type(error).__name__)


@contextmanager
def trace_run(*, connection=None, metadata=None):
    """An explicit harness context also captures interpretation before orchestration."""
    if existing := current_run():
        if metadata:
            existing.tag(**metadata)
        yield existing
        return
    run = RunTrace()
    run.tag(**(metadata or {}))
    token = _CURRENT.set(run)
    tracer = provider().get_tracer("copilot.observability")
    try:
        with tracer.start_as_current_span("enquiry", context=Context(), record_exception=False,
                                         set_status_on_exception=False,
                                         attributes={"copilot.span.kind": "run"}) as root:
            run.root = root
            run.trace_id = f"{root.get_span_context().trace_id:032x}"
            run.tag(**run.metadata)
            try:
                yield run
            except BaseException as error:
                run.tag(status="error")
                root.set_attribute("error.type", type(error).__name__)
                root.set_status(Status(StatusCode.ERROR, type(error).__name__))
                raise
            else:
                root.set_status(Status(StatusCode.OK))
            finally:
                from .costs import aggregate_usage
                try:
                    with run.lock:
                        run.closing = True
                        run.summary = aggregate_usage(list(run.spans.values()))
                    run.summary["export_mode"] = os.environ.get("COPILOT_TRACE_EXPORT", "local")
                    root.set_attribute("langfuse.trace.metadata", json.dumps({
                        **run.metadata, **run.summary,
                        "cost_inr": float(run.summary["cost_inr"]) if run.summary["cost_inr"] is not None else None,
                    }, sort_keys=True))
                    if run.metadata.get("bucket"):
                        root.set_attribute("langfuse.trace.tags", [f"bucket:{run.metadata['bucket']}"])
                    for key, value in run.summary.items():
                        if value is not None:
                            root.set_attribute(f"copilot.{key}", value)
                except Exception as error:
                    _LOG.warning("Trace cost calculation unavailable (%s)", type(error).__name__)
    finally:
        with run.lock:
            run.sealed = True
        _CURRENT.reset(token)
        if connection is not None:
            try:
                from .storage import save_run
                save_run(connection, run)
            except Exception as error:
                _LOG.warning("Trace persistence unavailable (%s)", type(error).__name__)


def traced_case(function):
    @wraps(function)
    def run(connection, *args, **kwargs):
        if os.environ.get("COPILOT_TRACING_ENABLED", "1") == "0":
            return function(connection, *args, **kwargs)
        with trace_run(connection=connection) as capture:
            result = function(connection, *args, **kwargs)
            capture.tag(case_id=result.get("case_id"), status=result.get("status"), step_count=result.get("step_count"))
            return result
    return run


def phase(name):
    """Instrument non-graph stages without modifying their returned contracts."""
    def decorate(function):
        @wraps(function)
        def call(*args, **kwargs):
            with observed_span(name):
                return function(*args, **kwargs)
        return call
    return decorate
