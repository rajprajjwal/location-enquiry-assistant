"""Per-enquiry trace filtering and span inspection in the staff interface."""
import json

import streamlit as st

from . import storage


def render(con):
    """Return whether instrumented runs exist and the selected trace ID."""
    all_rows = storage.list_runs(con, limit=-1)
    if not all_rows:
        return False, None
    st.subheader("Enquiry traces")
    columns = st.columns(3)
    selected = {}
    for column, key, label in zip(columns, ("bucket", "api", "team"), ("Bucket", "API", "Team")):
        values = sorted({row[key] or "(unassigned)" for row in all_rows})
        with column:
            value = st.selectbox(label, ["All", *values], key=f"trace_filter_{key}")
        selected[key] = None if value == "All" else value
    min_latency = max_latency = min_cost = max_cost = None
    with st.expander("Latency and cost filters"):
        if st.checkbox("Filter by latency"):
            min_latency = st.number_input("Minimum latency (ms)", min_value=0.0, value=0.0)
            max_latency = st.number_input("Maximum latency (ms)", min_value=0.0, value=120000.0)
        if st.checkbox("Filter by cost (INR)"):
            min_cost = st.number_input("Minimum cost (INR)", min_value=0.0, value=0.0, format="%.6f")
            max_cost = st.number_input("Maximum cost (INR)", min_value=0.0, value=100.0, format="%.6f")
            st.caption("Unpriced runs are excluded from numeric cost filters.")
    rows = storage.list_runs(con, **selected, min_latency_ms=min_latency, max_latency_ms=max_latency,
                             min_cost_inr=min_cost, max_cost_inr=max_cost, limit=-1)
    st.caption(f"{len(rows)} matching runs. Costs are shown in INR; latency is measured in milliseconds.")
    if not rows:
        st.info("No runs match these trace filters.")
        return True, None
    row = st.selectbox("Run", rows, key="instrumented_trace", format_func=lambda r: (
        f"{r['record_id'] or r['case_id'] or r['trace_id']} · {r['bucket'] or 'unassigned'} · {r['outcome']}"
    ))
    trace = storage.get_run(con, row["trace_id"])
    usage = trace["summary"]
    metrics = st.columns(4)
    metrics[0].metric("Latency (ms)", f"{trace['latency_ms']:,.1f}")
    cost_label = "Estimated reporting cost (INR)" if usage.get("cost_basis") == "illustrative" else "Endpoint cost (INR)"
    metrics[1].metric(cost_label, f"₹{trace['cost_inr']:.6f}" if trace["cost_inr"] is not None else "Unpriced")
    metrics[2].metric("LLM attempts", usage.get("model_attempts", 0))
    metrics[3].metric("Reported tokens", usage.get("input_tokens", 0) + usage.get("output_tokens", 0))
    if usage.get("actual_endpoint_charge_inr") == "0":
        st.caption("Actual institute endpoint charge: ₹0. Reporting estimates use illustrative rates.")
    st.caption(f"Pricing: {usage.get('cost_status', 'unpriced')}. Conversion: ₹{usage.get('usd_to_inr', '94')} per USD.")
    if usage.get("missing_usage_attempts"):
        st.caption(f"{usage['missing_usage_attempts']} endpoint attempts returned no complete usage. Token totals include reported usage only.")
    spans = trace["spans"]
    by_id = {span["span_id"]: span for span in spans}
    display = []
    for span in spans:
        depth, parent, seen = 0, span["parent_span_id"], set()
        while parent in by_id and parent not in seen:
            seen.add(parent)
            depth += 1
            parent = by_id[parent]["parent_span_id"]
        display.append({"Operation": "  " * depth + span["name"], "Type": span["kind"],
                        "Status": span["status"], "Latency (ms)": span["latency_ms"],
                        "Start offset (ms)": round((span["started_ns"] - trace["started_ns"]) / 1_000_000, 3)})
    st.dataframe(display, hide_index=True, use_container_width=True)
    with st.expander("Span attributes and IDs"):
        st.json(spans, expanded=False)
    st.download_button("Download trace JSON", json.dumps(trace, indent=2),
                       file_name=f"trace-{trace['trace_id']}.json", mime="application/json")
    return True, trace["trace_id"]
