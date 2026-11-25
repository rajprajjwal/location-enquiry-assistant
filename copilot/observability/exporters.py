"""Optional OTLP/HTTP export; local tracing does not need an external service."""
import base64
import logging
import os
from urllib.parse import urlsplit


_LOG = logging.getLogger(__name__)


def configure_remote(provider):
    mode = os.environ.get("COPILOT_TRACE_EXPORT", "local")
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
            base = values["LANGFUSE_BASE_URL"].rstrip("/")
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
        exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers, timeout=3)
        batch = BatchSpanProcessor(exporter, schedule_delay_millis=1000)
        from opentelemetry.sdk.trace import SpanProcessor
        class ActiveRunProcessor(SpanProcessor):
            def on_start(self, span, parent_context=None):
                pass

            def on_end(self, span):
                from .tracing import current_run
                run = current_run()
                if run is not None and not run.sealed and (not run.closing or span.parent is None):
                    batch.on_end(span)

            def shutdown(self):
                batch.shutdown()

            def force_flush(self, timeout_millis=30000):
                return batch.force_flush(timeout_millis)

        provider.add_span_processor(ActiveRunProcessor())
    except Exception as error:
        _LOG.warning("Remote tracing unavailable (%s); local spans remain enabled", type(error).__name__)
