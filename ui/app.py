import streamlit as st
import httpx
import json
import uuid

API_BASE = "http://localhost:8000"


class APIError(Exception):
    """Readable error for non-2xx or non-JSON API responses."""


def api_json(r: httpx.Response):
    """Decode a JSON API response, raising APIError with a readable message otherwise."""
    is_json = "application/json" in r.headers.get("content-type", "")
    body = None
    if is_json:
        try:
            body = r.json()
        except ValueError:
            is_json = False
    if r.is_success and is_json:
        return body
    if isinstance(body, dict):
        msg = body.get("detail") or body.get("error") or str(body)
    else:
        msg = (r.text or "").strip()[:300] or "empty response body"
    raise APIError(f"API returned HTTP {r.status_code}: {msg}")

st.set_page_config(page_title="Location Services Copilot", page_icon="📍", layout="wide")
st.title("📍 Location Services Copilot")

# ── Session state ──────────────────────────────────────────────────────────────
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "workflow" not in st.session_state:
    st.session_state.workflow = "sales"
if "has_pending" not in st.session_state:
    st.session_state.has_pending = False

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    workflow = st.radio(
        "Workflow",
        ["sales", "support"],
        format_func=lambda x: "💼 Sales" if x == "sales" else "🔧 Support",
    )
    st.session_state.workflow = workflow

    st.divider()
    params = {}
    if workflow == "sales":
        st.subheader("💼 Sales Context")
        with st.expander("Add context"):
            for field in ["company", "use_case", "device_count", "budget", "timeline"]:
                val = st.text_input(field.replace("_", " ").title())
                if val:
                    params[field] = val
    else:
        st.subheader("🔧 Diagnostic Params")
        with st.expander("Add parameters"):
            device_id  = st.text_input("device_id")
            lat        = st.text_input("lat")
            lon        = st.text_input("lon")
            timestamp  = st.text_input("timestamp (ISO8601)")
            error_code = st.text_input("error_code")
            if device_id:  params["device_id"]  = device_id
            if timestamp:  params["timestamp"]   = timestamp
            if error_code: params["error_code"]  = error_code
            if lat:
                try: params["lat"] = float(lat)
                except ValueError: pass
            if lon:
                try: params["lon"] = float(lon)
                except ValueError: pass

    st.divider()
    if st.button("🆕 New Conversation"):
        st.session_state.conversation_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.has_pending = False
        st.rerun()
    st.caption(f"Session: `{st.session_state.conversation_id[:8]}...`")

    st.divider()
    st.subheader("📋 Tracker")
    if st.button("Refresh Tracker"):
        try:
            r = httpx.get(f"{API_BASE}/tracker/{st.session_state.conversation_id}")
            data = api_json(r)
            st.json(data)
            st.session_state.has_pending = bool(data.get("pending_updates"))
        except Exception as e:
            st.error(str(e))

    if st.session_state.has_pending:
        if st.button("✅ Approve Pending Updates", type="primary"):
            try:
                r = httpx.post(f"{API_BASE}/approve-update",
                               json={"conversation_id": st.session_state.conversation_id})
                st.success(f"Approved: {api_json(r)}")
                st.session_state.has_pending = False
            except Exception as e:
                st.error(str(e))

    st.divider()
    st.subheader("🔍 Audit Trail")
    if st.button("View Audit Trail"):
        try:
            r = httpx.get(f"{API_BASE}/audit/{st.session_state.conversation_id}")
            st.json(api_json(r))
        except Exception as e:
            st.error(str(e))

# ── Main tabs ──────────────────────────────────────────────────────────────────
tab_chat, tab_baseline = st.tabs(["💬 Agentic Copilot", "🧪 Prompt Engineering Baseline"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Agentic Copilot Chat
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander("📚 KB Sources"):
                    for s in msg["sources"]:
                        st.caption(f"**{s['ref']}** (score: {s['score']:.2f}): {s['content']}")
            if msg.get("planner"):
                with st.expander("🧠 Planner Output"):
                    st.json(msg["planner"])
            if msg.get("critic"):
                with st.expander("🔎 Critic Review"):
                    approved   = msg["critic"].get("approved", True)
                    confidence = msg["critic"].get("confidence", 1.0)
                    color = "green" if approved else "red"
                    st.markdown(f"**Approved:** :{color}[{'✓' if approved else '✗'}]  |  **Confidence:** {confidence:.0%}")
                    if msg["critic"].get("issues"):
                        st.warning("Issues: " + ", ".join(msg["critic"]["issues"]))
                    if msg["critic"].get("unsupported_claims"):
                        st.error("Unsupported: " + ", ".join(msg["critic"]["unsupported_claims"]))
            if msg.get("pending_updates"):
                st.warning(f"⏳ Pending tracker update — click **Approve** in sidebar")

    if prompt := st.chat_input("Ask about location services..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        payload = {
            "conversation_id": st.session_state.conversation_id,
            "workflow": st.session_state.workflow,
            "message": prompt,
            "params": params if params else None,
        }

        with st.chat_message("assistant"):
            with st.spinner("Running Planner → Executor → Critic..."):
                try:
                    r = httpx.post(f"{API_BASE}/chat", json=payload, timeout=120)
                    data = api_json(r)
                    response_text = data.get("response", "No response generated.")
                    st.markdown(response_text)

                    sources = data.get("sources", [])
                    if sources:
                        with st.expander("📚 KB Sources"):
                            for s in sources:
                                st.caption(f"**{s['ref']}** (score: {s['score']:.2f}): {s['content']}")

                    planner = data.get("planner", {})
                    if planner:
                        with st.expander("🧠 Planner Output"):
                            st.json(planner)

                    critic = data.get("critic", {})
                    if critic:
                        with st.expander("🔎 Critic Review"):
                            approved   = critic.get("approved", True)
                            confidence = critic.get("confidence", 1.0)
                            color = "green" if approved else "red"
                            st.markdown(f"**Approved:** :{color}[{'✓' if approved else '✗'}]  |  **Confidence:** {confidence:.0%}")
                            if critic.get("issues"):
                                st.warning("Issues: " + ", ".join(critic["issues"]))

                    pending = data.get("pending_tracker_updates", {})
                    if pending:
                        st.warning("⏳ Pending tracker update — click **Approve** in sidebar")
                        st.session_state.has_pending = True

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_text,
                        "sources": sources,
                        "planner": planner,
                        "critic": critic,
                        "pending_updates": pending,
                    })

                except httpx.ConnectError:
                    st.error("Cannot connect to API. Start the server: `python run_api.py`")
                except Exception as e:
                    st.error(f"Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Prompt Engineering Baseline
# ══════════════════════════════════════════════════════════════════════════════
with tab_baseline:
    st.subheader("🧪 Prompt Engineering Baseline")
    st.markdown(
        "Runs the **same query** through three prompting strategies simultaneously "
        "with no agentic loop, no RAG, and no tools. Compares output quality, "
        "latency, and failure modes."
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        baseline_query = st.text_area(
            "Query",
            value="We need to track 500 delivery vehicles in real time across Europe. "
                  "We're not sure which plan fits our budget.",
            height=80,
        )
    with col2:
        baseline_workflow = st.radio("Workflow", ["sales", "support"], key="bl_wf")
        run_btn = st.button("▶ Run Baseline", type="primary", use_container_width=True)

    # Sample queries
    st.caption("Quick examples:")
    ex_cols = st.columns(3)
    examples = [
        ("Sales — qualification",
         "We need to track 500 delivery vehicles in real time across Europe. Not sure which plan fits."),
        ("Support — 422 error",
         "Getting 422 errors on every location API call. device_id is truck-001."),
        ("Capability comparison",
         "How does your indoor positioning accuracy compare to competitors for a warehouse?"),
    ]
    for i, (label, ex_query) in enumerate(examples):
        if ex_cols[i].button(label, use_container_width=True):
            st.session_state["bl_query_override"] = ex_query
            st.rerun()

    if "bl_query_override" in st.session_state:
        baseline_query = st.session_state.pop("bl_query_override")

    if run_btn:
        with st.spinner("Running 3 strategies in parallel... (CoT runs 3 samples — takes ~30s)"):
            try:
                r = httpx.post(
                    f"{API_BASE}/baseline",
                    json={"query": baseline_query, "workflow": baseline_workflow},
                    timeout=180,
                )
                data = api_json(r)

                # ── Winner banner ──────────────────────────────────────────
                winner_map = {
                    "few_shot_structured_output":       "Strategy 1 — Few-Shot Structured Output",
                    "chain_of_thought_self_consistency": "Strategy 2 — Chain-of-Thought + Self-Consistency",
                    "decomposition_prompting":           "Strategy 3 — Decomposition Prompting",
                }
                st.success(f"🏆 Winner: **{winner_map.get(data['winner'], data['winner'])}**")

                # ── Comparison table ───────────────────────────────────────
                st.subheader("📊 Comparison Table")
                table = data.get("comparison_table", [])
                cols = st.columns(4)
                cols[0].markdown("**Strategy**")
                cols[1].markdown("**Score /4**")
                cols[2].markdown("**Latency**")
                cols[3].markdown("**Failure**")
                for row in table:
                    c0, c1, c2, c3 = st.columns(4)
                    name_map = {
                        "few_shot_structured_output":       "1 — Few-Shot",
                        "chain_of_thought_self_consistency": "2 — CoT+SC",
                        "decomposition_prompting":           "3 — Decomposition",
                    }
                    c0.write(name_map.get(row["strategy"], row["strategy"]))
                    score_color = "🟢" if row["score"] >= 3 else "🟡" if row["score"] == 2 else "🔴"
                    c1.write(f"{score_color} {row['score']}/4")
                    c2.write(f"{row['latency_s']}s")
                    c3.write(row["failure"] or "✓ none")

                st.divider()

                # ── Per-strategy detail ────────────────────────────────────
                strategy_labels = {
                    "few_shot_structured_output":       "Strategy 1 — Few-Shot Structured Output",
                    "chain_of_thought_self_consistency": "Strategy 2 — Chain-of-Thought + Self-Consistency",
                    "decomposition_prompting":           "Strategy 3 — Decomposition Prompting",
                }
                for s in data.get("strategies", []):
                    label = strategy_labels.get(s["strategy"], s["strategy"])
                    is_winner = s["strategy"] == data["winner"]
                    header = f"{'🏆 ' if is_winner else ''}{label}"
                    with st.expander(header, expanded=is_winner):
                        r_data = s.get("result", {})

                        if r_data.get("parse_error"):
                            st.error("⚠️ JSON parse failed — raw output below")
                            st.code(r_data.get("raw", ""), language="text")
                        else:
                            col_a, col_b = st.columns(2)
                            col_a.metric("Intent", r_data.get("intent", "—"))
                            col_a.metric("Confidence", f"{r_data.get('confidence', 0):.0%}")
                            col_b.metric("Missing Info Fields", len(r_data.get("missing_info", [])))
                            col_b.metric("Latency", f"{s['latency_s']}s")

                            if r_data.get("summary"):
                                st.markdown(f"**Summary:** {r_data['summary']}")
                            if r_data.get("recommended_action"):
                                st.info(f"**Recommended Action:** {r_data['recommended_action']}")
                            if r_data.get("missing_info"):
                                st.markdown("**Missing Info:** " + ", ".join(f"`{m}`" for m in r_data["missing_info"]))

                        # CoT-specific: show agreement rate
                        if s["strategy"] == "chain_of_thought_self_consistency":
                            agreement = s.get("agreement_rate", 0)
                            color = "green" if agreement >= 0.67 else "orange" if agreement >= 0.34 else "red"
                            st.markdown(f"**Sample intents:** {s.get('sample_intents', [])}")
                            st.markdown(f"**Agreement rate:** :{color}[{agreement:.0%}]")

                        # Decomposition: show sub-answers
                        if s["strategy"] == "decomposition_prompting" and s.get("sub_answers"):
                            with st.expander("🔬 Sub-problem answers"):
                                for k, v in s["sub_answers"].items():
                                    st.markdown(f"**{k}:** {v}")

                        if s.get("failure"):
                            st.error(f"⚠️ Failure: {s['failure']}")
                        if s.get("failure_mode_ref"):
                            st.caption(f"Failure mode: {s['failure_mode_ref']}")

                st.divider()

                # ── Failure modes catalogue ────────────────────────────────
                with st.expander("📋 Documented Failure Modes (Qwen3-8B)"):
                    st.markdown(
                        "These are observed failure patterns when running Qwen3-8B "
                        "as a single-agent without an agentic loop or Critic:"
                    )
                    for mode, desc in data.get("failure_modes_catalogue", {}).items():
                        st.markdown(f"- **`{mode}`** — {desc}")

            except httpx.ConnectError:
                st.error("Cannot connect to API. Start the server: `python run_api.py`")
            except Exception as e:
                st.error(f"Error: {e}")
