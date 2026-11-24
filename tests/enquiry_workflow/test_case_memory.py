from contextlib import closing
from unittest.mock import Mock

from copilot.enquiry_workflow.case_memory import load_conversation
from copilot.enquiry_workflow.cases import run_case
from copilot.enquiry_workflow.deletion import delete_enquiry
from copilot.case_storage.db import connect
from copilot.registered_tools.tool_registry import DocumentSearchTool
from tests.support.helpers import completion, model_json


def _setup():
    client = Mock()
    reply = completion(model_json(intent="docs_how_to", sub_intent="parameter_question",
                                  api="directions", team="Support"))

    def answer(messages, **_options):
        prompt = messages[-1]["content"]
        if '"passages"' in prompt:
            return completion('{"passages":[1]}')
        if '"candidate"' in prompt:
            return completion('{"answers_enquiry":true}')
        if "Germany" in prompt:
            return completion(model_json(
                intent="docs_how_to", sub_intent="parameter_question", api="directions", team="Support",
                qualification={"region": {"value": "Germany", "evidence": "Germany"}},
            ))
        return reply

    client.complete.side_effect = answer
    search = DocumentSearchTool(search_function=lambda _: [
        {"source_url": "https://example.test/directions", "relevant_passage": "Set intermediate stops as waypoints."},
    ])
    return client, search


def test_same_case_restart_recovers_the_question_and_answer(tmp_path):
    path = tmp_path / "cases.db"
    client, search = _setup()
    with closing(connect(path)) as con:
        first = run_case(con, "How do I set waypoints in the Directions API?", client=client, search=search)
        assert first["status"] == "clarification_needed"

    with closing(connect(path)) as con:
        second = run_case(con, "Mapbox.", case_id=first["case_id"], client=client, search=search)
        assert second["status"] == "final"
        assert second["conversation_state"]["known_facts"]["current_provider"] == "Mapbox"
        assert second["conversation_state"]["questions_answered"] == ["current_provider"]

    with closing(connect(path)) as con:
        resumed = run_case(con, "Can I pass waypoints in the Directions API?", case_id=first["case_id"],
                           client=client, search=search)
        other = run_case(con, "Can I pass waypoints in the Directions API?", client=client, search=search)
        assert resumed["status"] == "final" and not resumed["clarifying_questions"]["needed"]
        assert other["status"] == "clarification_needed"
        assert "current_provider" not in other["conversation_state"]["known_facts"]


def test_same_case_restart_recovers_corrections_and_diagnostics(tmp_path):
    path = tmp_path / "cases.db"
    client, search = _setup()
    with closing(connect(path)) as con:
        first = run_case(con, "We use Mapbox Directions in India. We already retried the request.",
                         client=client, search=search)
        case_id = first["case_id"]
        second = run_case(con, "Correction: we use Google Maps Directions in Germany. We already retried the request.",
                          case_id=case_id, client=client, search=search)

    with closing(connect(path)) as con:
        state = load_conversation(con, case_id)
        assert state.known_facts["region"] == "Germany"
        assert state.known_facts["current_provider"] == "Google Maps Platform"
        assert state.diagnostic_history == ["We already retried the request"]
        assert "Germany" in state.conversation_summary
        assert any(row["field"] == "region" for row in state.corrections)
        assert state.updated_at == second["conversation_state"]["updated_at"]
        delete_enquiry(con, second["trace_id"])
        assert load_conversation(con, case_id).known_facts["region"] == "India"
