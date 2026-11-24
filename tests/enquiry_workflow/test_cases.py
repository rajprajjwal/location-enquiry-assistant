from contextlib import closing
from unittest.mock import create_autospec

from copilot.model_gateway.client import LLMClient
from copilot.enquiry_workflow.cases import run_case
from copilot.enquiry_workflow.deletion import delete_enquiry
from copilot.case_storage import cases, handlers, traces
from copilot.case_storage.db import connect
from copilot.registered_tools.tool_registry import DocumentSearchTool
from tests.support.helpers import completion, model_json


def test_escalation_can_be_reviewed_after_reopening_the_database(tmp_path):
    db_path = tmp_path / "cases.db"
    client = create_autospec(LLMClient, instance=True)
    client.complete.return_value = completion(model_json(
        intent="troubleshooting", sub_intent="production_incident", api="directions", team="Support",
    ))
    with closing(connect(db_path)) as con:
        result = run_case(
            con, "Production is down. Directions returns 503 for all requests. Email test@example.com.",
            client=client, search=DocumentSearchTool(documents=[]),
        )

    with closing(connect(db_path)) as con:
        case_id = result["case_id"]
        assert cases.get_case(con, case_id)["status"] == "awaiting_approval"
        assert "test@example.com" not in cases.get_case_history(con, case_id)[0]["content"]
        trace = traces.get_trace(con, result["trace_id"])
        assert [step["step"] for step in trace["steps"]] == [
            "follow_up_selection", "plan", "route_evidence", "document_search", "conversation_state", "outcome",
        ]
        action, = cases.list_pending(con, case_id)
        assert action["payload"]["owner"] == "Maps engineering"
        handlers.approve_and_apply(con, action["id"], approver="deepshikha", note="Confirmed incident")
        assert cases.get_case(con, case_id)["status"] == "escalated"
        assert cases.list_pending(con, case_id) == []
        assert cases.decision_log(con)[0]["note"] == "Confirmed incident"



def test_delete_legacy_enquiry_removes_only_its_turn(tmp_path):
    client = create_autospec(LLMClient, instance=True)
    client.complete.return_value = completion(model_json(
        intent="docs_how_to", sub_intent="parameter_question", api="directions", team="Support",
    ))
    with closing(connect(tmp_path / "cases.db")) as con:
        question = "How do I set waypoints in the Directions API?"
        first = run_case(con, question, client=client)
        second = run_case(con, question, case_id=first["case_id"], client=client)
        con.execute("UPDATE messages SET turn_trace_id = NULL WHERE turn_trace_id = ?", (first["trace_id"],))
        con.commit()

        delete_enquiry(con, first["trace_id"])

        history = cases.get_case_history(con, first["case_id"])
        assert [message["role"] for message in history] == ["user", "clarification"]
        assert traces.get_trace(con, first["trace_id"]) is None
        assert traces.get_trace(con, second["trace_id"]) is not None
        assert cases.load_state(con, first["case_id"])["last_trace_id"] == second["trace_id"]


def test_deleting_last_enquiry_source_cancels_pending_approval(tmp_path):
    client = create_autospec(LLMClient, instance=True)
    client.complete.return_value = completion(model_json(
        intent="troubleshooting", sub_intent="production_incident", api="directions", team="Support",
    ))
    with closing(connect(tmp_path / "cases.db")) as con:
        result = run_case(con, "Production is down. Directions returns 503 for all requests.", client=client)
        action, = cases.list_pending(con, result["case_id"])
        # Simulate an older record without an explicit source link.
        con.execute("DELETE FROM approval_enquiry_sources")
        con.commit()

        delete_enquiry(con, result["trace_id"])

        assert cases.list_pending(con, result["case_id"]) == []
        assert cases.get_action(con, action["id"])["status"] == "cancelled"
        assert cases.get_case(con, result["case_id"])["status"] == "open"
        assert traces.get_trace(con, result["trace_id"]) is None


def test_shared_pending_approval_uses_remaining_source_after_deletion(tmp_path):
    client = create_autospec(LLMClient, instance=True)
    client.complete.return_value = completion(model_json(
        intent="troubleshooting", sub_intent="production_incident", api="directions", team="Support",
    ))
    with closing(connect(tmp_path / "cases.db")) as con:
        first = run_case(con, "Production is degraded. Directions returns 503 for some requests.", client=client)
        action, = cases.list_pending(con, first["case_id"])
        second = run_case(
            con, "Production is down. Directions returns 503 for all requests.",
            case_id=first["case_id"], client=client,
        )
        updated, = cases.list_pending(con, first["case_id"])
        assert updated["id"] == action["id"]
        assert updated["payload"]["severity"] == "SEV1"

        delete_enquiry(con, second["trace_id"])

        remaining, = cases.list_pending(con, first["case_id"])
        assert remaining["id"] == action["id"]
        assert remaining["payload"] == action["payload"]
        delete_enquiry(con, first["trace_id"])
        assert cases.list_pending(con, first["case_id"]) == []


def test_deleted_source_is_marked_on_decided_approval(tmp_path):
    client = create_autospec(LLMClient, instance=True)
    client.complete.return_value = completion(model_json(
        intent="troubleshooting", sub_intent="production_incident", api="directions", team="Support",
    ))
    with closing(connect(tmp_path / "cases.db")) as con:
        result = run_case(con, "Production is down. Directions returns 503 for all requests.", client=client)
        action, = cases.list_pending(con, result["case_id"])
        handlers.approve_and_apply(con, action["id"], approver="deepshikha", note="Confirmed incident")
        original, = cases.decision_log(con)

        delete_enquiry(con, result["trace_id"])

        decision, = cases.decision_log(con)
        for field in ("decision", "reviewer", "decided_at", "note", "final", "applied_at"):
            assert decision[field] == original[field]
        assert decision["source_enquiry_deleted"] is True
        source, = decision["source_enquiries"]
        assert source["trace_id"] == result["trace_id"]
        assert source["deleted_at"]
