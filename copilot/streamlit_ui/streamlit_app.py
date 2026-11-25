# Source history: Deepshikha (746a299), deepshikha/lbs-copilot. See copilot/enquiry_workflow/source-history.json.
"""Local tester for the LangGraph support and escalation flow."""

from contextlib import closing
import json

import streamlit as st

from copilot.enquiry_workflow.cases import run_case
from copilot.enquiry_workflow.deletion import delete_enquiry
from copilot.response_drafting.customer_response import format_customer_response
from copilot.enquiry_workflow.retrieval import (
    rag_document_search, retrieval_setup_issues, warm_retrieval_runtime, RetrievalUnavailable,
)
from copilot.case_storage import cases, handlers, traces
from copilot.case_storage.db import DB_PATH, connect
from copilot.observability.viewer import render as render_trace_explorer

@st.cache_resource(show_spinner=False)
def load_hybrid_runtime():
    warm_retrieval_runtime()
    return True


st.set_page_config(page_title="Location Enquiry Assistant", layout="wide")
st.title("Location Enquiry Assistant")

query_tab, review_tab, trace_tab = st.tabs(["Enquiries", "Approvals", "Traces"])

with closing(connect(DB_PATH)) as con:
    with query_tab:
        saved = {case["id"]: case for case in cases.list_cases(con, limit=-1)}
        opened = st.session_state.pop("open_case_after_submit", None)
        if opened in saved:
            st.session_state["selected_case"] = opened
        case_id = st.selectbox(
            "Customer case", [None, *saved],
            format_func=lambda value: "New case" if value is None else f"{saved[value]['customer']} · {value}",
            key="selected_case",
        )
        state = cases.load_state(con, case_id) if case_id else {}
        if case_id:
            with st.expander("Conversation history", expanded=True):
                labels = {"user": "Customer", "clarification": "Assistant", "draft": "Draft"}
                for message in cases.get_case_history(con, case_id, limit=-1):
                    st.text(f"{labels.get(message['role'], message['role'])}: {message['content']}")

        mode = st.radio("Retrieval", ["BM25", "Hybrid with reranking"], horizontal=True)
        hybrid_issues = retrieval_setup_issues() if mode == "Hybrid with reranking" else []
        if mode == "Hybrid with reranking" and not hybrid_issues:
            try:
                with st.spinner("Preparing hybrid retrieval before starting an enquiry…"):
                    load_hybrid_runtime()
            except RetrievalUnavailable as exc:
                hybrid_issues = [str(exc)]
            except Exception:
                hybrid_issues = ["Hybrid retrieval could not initialize. Check the embedding service, local model assets and dense index with the setup check command."]
        if hybrid_issues:
            st.warning("Hybrid retrieval is unavailable. " + " ".join(hybrid_issues))
            st.caption("Choose BM25 to run this enquiry now.")
        turn = st.session_state.setdefault("enquiry_input_turn", 0)
        with st.form("enquiry"):
            customer = st.text_input("Customer name or reference") if case_id is None else None
            customer_status = st.selectbox(
                "Confirmed customer relationship",
                [None, "existing", "new"],
                format_func=lambda value: {None: "Use saved evidence / not confirmed", "existing": "Existing customer", "new": "New customer"}[value],
                key=f"customer_status_{case_id}_{turn}",
                help="Select only when confirmed by the customer or an account record. A named provider or forecast volume does not confirm the relationship.",
            )
            query = st.text_area(
                "Customer enquiry", key=f"customer_enquiry_{case_id}_{turn}",
                placeholder="Enter the customer's reply" if state.get("pending_clarification") or state.get("pending_provider_question") else None,
            )
            submitted = st.form_submit_button("Run enquiry", disabled=bool(hybrid_issues))

        if submitted:
            try:
                search = rag_document_search(mode="bm25", rerank=False) if mode == "BM25" else None
                with st.spinner("Running enquiry"):
                    result = run_case(con, query, case_id=case_id, customer=customer, search=search,
                                      confirmed_customer_status=customer_status)
            except ValueError as exc:
                st.error(str(exc))
            else:
                # A fresh widget gives the next turn an empty input box.
                st.session_state["enquiry_input_turn"] = turn + 1
                st.session_state["open_case_after_submit"] = result["case_id"]
                st.rerun()

        result = state.get("last_result")
        if result:
            st.caption(f"Case {result['case_id']} · {result['step_count']} steps")
            ownership = result.get("ownership_review", {})
            if ownership.get("provisional"):
                st.info(ownership["reason"])
                if ownership.get("suggested_question"):
                    st.caption(ownership["suggested_question"])
            response = result.get('customer_response') or format_customer_response(result)
            st.subheader('Customer response')
            st.markdown(response['markdown'])
            if result["status"] == "clarification_needed":
                st.caption("Enter the customer’s reply in the enquiry box above.")
            draft = result.get('response_draft') or {}
            if draft.get('citations'):
                with st.expander('Citation evidence'):
                    st.json(result['response_draft']['citations'], expanded=False)
            staff_questions = result["outputs"].get("clarifying_questions", {}).get("questions", [])
            active_text = {question["text"] for question in result["clarifying_questions"]["questions"]}
            suggestions = [question["text"] for question in staff_questions if question["text"] not in active_text]
            if suggestions:
                with st.expander("Suggested follow-up questions"):
                    for question in suggestions:
                        st.text(question)
            if result["outputs"]:
                with st.expander("Structured output"):
                    st.json(result["outputs"], expanded=False)
            if evidence := result.get("route_evidence"):
                with st.expander("Supporting evidence"):
                    if price := evidence.get("list_price_baseline"):
                        st.text(price["draft_text"])
                        st.json(price["citations"], expanded=False)
                    if passages := evidence.get("retrieved_passages"):
                        st.json(passages, expanded=False)
            if result["proposed_actions"] and cases.list_pending(con, case_id):
                st.info("A proposal is pending human review. See Approvals.")
            st.caption(f"Critic verdict: {result['critic']['verdict']}")

    with review_tab:
        pending = [action for action in cases.list_pending(con) if action["type"] in {"escalation", "record_update"}]
        if pending:
            action = st.selectbox(
                "Pending proposal", pending,
                format_func=lambda item: (
                    f"#{item['id']} · {item['case_id']} · "
                    f"{item['payload'].get('owner') or item['payload'].get('record_id')}"
                ),
            )
            eligible = [name for name in cases.approver_names() if cases.can_approve(name, action["type"])]
            st.json(action["payload"])
            if eligible:
                with st.form("review"):
                    reviewer = st.selectbox("Reviewer", eligible)
                    record_update = action["type"] == "record_update"
                    if record_update:
                        edited = st.text_area("Proposed fields", value=json.dumps(action["payload"]["fields"], indent=2))
                    else:
                        edited = st.text_area("Handoff summary", value=action["payload"].get("summary", ""))
                    note = st.text_input("Decision note")
                    approve = st.form_submit_button("Approve")
                    reject = st.form_submit_button("Reject")
                try:
                    if approve:
                        handlers.approve_and_apply(
                            con, action["id"], approver=reviewer, note=note,
                            edited_payload={
                                **action["payload"],
                                **({"fields": json.loads(edited)} if record_update else {"summary": edited}),
                            },
                        )
                        st.rerun()
                    if reject:
                        handlers.reject(con, action["id"], approver=reviewer, note=note)
                        st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            else:
                st.info("No reviewer is configured for this proposal.")
        else:
            st.info("No proposals awaiting review.")
        st.subheader("Decision log")
        decisions = cases.decision_log(con)
        for decision in decisions:
            if decision["source_enquiry_deleted"]:
                st.caption(f"Approval #{decision['action_id']} · Source enquiry deleted")
        st.json(decisions, expanded=False)

    with trace_tab:
        if st.session_state.pop("enquiry_deleted", False):
            st.success("Enquiry and local traces deleted. Langfuse deletion is tracked separately.")
        from copilot.observability.storage import initialize as initialize_observability
        initialize_observability(con)
        deletion_count = con.execute("SELECT COUNT(*) FROM observability_trace_deletions WHERE status='pending'").fetchone()[0]
        if deletion_count:
            st.info(f"{deletion_count} Langfuse trace deletion requests need retrying.")
            if st.button("Retry Langfuse trace deletions"):
                from copilot.observability.sync_deletions import process_pending_deletions
                process_pending_deletions(con)
                st.rerun()
        has_observability, selected_trace = render_trace_explorer(con)
        rows = traces.list_traces(con, limit=-1)
        if has_observability:
            rows = [row for row in rows if row["id"] == selected_trace]
        if rows:
            row = rows[0] if has_observability else st.selectbox(
                "Run", rows, format_func=lambda value: f"{value['ts']} · {value['case_id']}",
            )
            trace = traces.get_trace(con, row["id"])
            st.text(trace["query"])
            for step in trace["steps"]:
                with st.expander(step["step"]):
                    if step["ms"] is not None:
                        st.caption(f"{step['ms']} ms")
                    st.code(step["output_json"], language="json")
            if trace["citations"]:
                st.json(trace["citations"], expanded=False)
            if trace["case_id"]:
                with st.expander("Delete enquiry and traces"):
                    confirm = st.checkbox(
                        "Permanently delete this enquiry, its reply and all trace steps. Cancel pending approvals with no other source. Keep recorded decisions.",
                        key=f"confirm_delete_{trace['id']}",
                    )
                    if st.button("Delete enquiry and traces", disabled=not confirm, key=f"delete_{trace['id']}"):
                        try:
                            delete_enquiry(con, trace["id"])
                        except ValueError as exc:
                            st.error(str(exc))
                        else:
                            st.session_state["enquiry_deleted"] = True
                            st.rerun()
        elif not has_observability:
            st.info("Run an enquiry to see its trace.")
