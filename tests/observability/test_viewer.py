"""Trace filters must change the displayed run set, including INR bounds."""
from contextlib import closing
from pathlib import Path

from streamlit.testing.v1 import AppTest

from copilot.case_storage.db import connect
from copilot.observability import trace_run, observed_span
from copilot.observability import costs
from copilot.observability.costs import Rates
from copilot.observability.tracing import set_usage


def test_bucket_and_cost_filters_control_run_picker(tmp_path, monkeypatch):
    rates = Rates(input_usd_per_million=1, output_usd_per_million=0, source="UI test fixture")
    monkeypatch.setattr(costs, "configured_rates", lambda: rates)
    database = tmp_path / "viewer.db"
    with closing(connect(database)) as con:
        for bucket, tokens in (("docs", 1_000_000), ("qualification", 2_000_000)):
            with trace_run(connection=con, metadata={"bucket": bucket, "record_id": f"synthetic-{bucket}"}):
                with observed_span("llm.request", kind="llm_attempt") as span:
                    set_usage(span, {"prompt_tokens": tokens, "completion_tokens": 0})
    app = tmp_path / "viewer.py"
    app.write_text("from copilot.case_storage.db import connect\n"
                   "from copilot.observability.viewer import render\n"
                   f"con=connect({str(database)!r})\nrender(con)\ncon.close()\n")
    ui = AppTest.from_file(str(app)).run()
    assert not ui.exception
    assert len(ui.selectbox(key="instrumented_trace").options) == 2
    ui.selectbox(key="trace_filter_bucket").set_value("docs").run()
    assert len(ui.selectbox(key="instrumented_trace").options) == 1
    assert "synthetic-docs" in ui.selectbox(key="instrumented_trace").options[0]
    ui.selectbox(key="trace_filter_bucket").set_value("All").run()
    next(item for item in ui.checkbox if item.label == "Filter by cost (INR)").check().run()
    assert len(ui.selectbox(key="instrumented_trace").options) == 1
    next(item for item in ui.number_input if item.label == "Maximum cost (INR)").set_value(0.0).run()
    assert any("No runs match" in item.value for item in ui.info)
    assert not ui.exception
