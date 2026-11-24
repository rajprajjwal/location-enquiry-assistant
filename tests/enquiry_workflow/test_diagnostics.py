import json
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from copilot.case_storage import cases
from copilot.case_storage.db import connect
from copilot.diagnostics.evaluation import bind_review, score_bound_review
from copilot.diagnostics.facts import build_diagnostic_state
from copilot.diagnostics.planning import plan_staff_follow_up
from copilot.diagnostics.policy import allowed_decisions
from copilot.enquiry_workflow.case_memory import load_conversation


def test_legacy_conversation_rebuilds_diagnostic_values(tmp_path):
    with closing(connect(tmp_path / "legacy.db")) as con:
        case_id = cases.create_case(con)
        cases.add_message(con, case_id, "user", "OSRM returns HTTP 400 for coordinates 12.1,77.2.")
        state = load_conversation(con, case_id).diagnostic_state
        assert state["facts"]["coordinates"]["value"] == "12.1,77.2"
        assert state["facts"]["http_status"]["value"] == ["400"]
        assert load_conversation(con, case_id).diagnostic_state == state


def test_shared_facts_preserve_false_values_and_redact_request_secrets():
    state = build_diagnostic_state({"query": "We do not send a User-Agent.\nRequest URL: https://example.test?token=abc123"})
    assert state.facts["user_agent_present"].value is False
    assert "abc123" not in state.model_dump_json()
    assert state.facts["request_example"].value.endswith("token=[REDACTED]")


def test_current_qualification_state_removes_stale_values():
    previous = build_diagnostic_state({
        "query": "Earlier context", "known_facts": [{"field": "region", "value": "India", "source": "state_store"}],
    })
    updated = build_diagnostic_state({"query": "Leave the region open.", "known_facts": []}, previous.model_dump())
    assert "region" not in updated.facts


def test_raw_diagnostic_facts_do_not_change_interpretation_prompt():
    from copilot.enquiry_interpretation import interpret
    from tests.support.helpers import completion, model_json

    query = "OSRM returns HTTP 400 for coordinates 12.1,77.2."
    first, second = Mock(), Mock()
    for client in (first, second):
        client.complete.return_value = completion(model_json(
            intent="troubleshooting", sub_intent="parameter_question", api="directions", team="Support",
        ))
    interpret({"query": query}, client=first)
    interpret({"query": query}, client=second,
              diagnostics=build_diagnostic_state({"query": query}).model_dump(mode="json"))
    assert first.complete.call_args_list == second.complete.call_args_list


def test_planner_receives_evidence_and_preserves_active_route():
    enquiry = {"query": "The request returns 422."}
    state = build_diagnostic_state(enquiry)
    active = {"field": "provider", "text": "Which provider?"}
    result = {
        "status": "clarification_needed",
        "clarifying_questions": {"needed": True, "questions": [active]},
        "response_draft": {"draft_text": "A documented parameter explanation."},
        "outputs": {"next_action": {"action_type": "ask_clarifying_questions"}},
        "diagnostic_context": {
            "state": state.model_dump(mode="json"),
            "retrieved_evidence": [{"source_url": "https://docs.example.test", "relevant_passage": "Invalid input returns 422."}],
        },
    }
    client = Mock()
    client.complete.return_value = SimpleNamespace(
        finish_reason="stop", text='{"decision":"rejected_request","reason":"Inspect the rejected input and error body."}',
    )
    updated = plan_staff_follow_up(result, enquiry, client=client)
    payload = json.loads(client.complete.call_args.args[0][-1]["content"])
    assert payload["retrieved_evidence"][0]["source_url"] == "https://docs.example.test"
    assert payload["draft"] == "A documented parameter explanation."
    assert updated["follow_up_selection"]["facts"] == ["request_example", "error_message"]
    assert updated["status"] == result["status"]
    assert updated["clarifying_questions"] == result["clarifying_questions"]
    assert updated["outputs"]["next_action"] == result["outputs"]["next_action"]


def test_planner_does_not_reask_a_supplied_provider():
    enquiry = {"query": "Mapbox predictions are absent."}
    state = build_diagnostic_state(enquiry)
    result = {
        "clarifying_questions": {"needed": False, "questions": []}, "outputs": {},
        "diagnostic_context": {"state": state.model_dump(mode="json"), "retrieved_evidence": []},
    }
    client = Mock()
    client.complete.return_value = SimpleNamespace(
        finish_reason="stop", text='{"decision":"prediction_request","reason":"Inspect the submitted options."}',
    )
    updated = plan_staff_follow_up(result, enquiry, client=client)
    assert updated["follow_up_selection"]["facts"] == ["request_body"]
    assert "provider" not in updated["outputs"]["clarifying_questions"]["questions"][0]["text"]


def test_evaluation_binding_accepts_new_matches_and_rejects_stale_outputs(tmp_path):
    predictions, gold = tmp_path / "predictions.jsonl", tmp_path / "gold.json"
    predictions.write_text(json.dumps({"record_id": "example", "questions": {"method": ["Share the request and error?"]}}) + "\n")
    gold.write_text(json.dumps({"cases": [{"record_id": "example", "questions": [
        {"question": "Share the request and error?", "facts": ["request", "error"]},
    ]}]}))
    judgements = [{"record_id": "example", "methods": {"method": {
        "whole": [[1, 1]], "facts": [[1, 1, 1], [1, 1, 2]],
    }}}]
    review = bind_review(predictions, gold, judgements, reviewer="test reviewer")
    metrics = score_bound_review(predictions, gold, review)["method"]
    assert metrics["f1"] == metrics["fact_recall"] == 1
    predictions.write_text(predictions.read_text().replace("Share", "Provide"))
    with pytest.raises(ValueError, match="different predictions"):
        score_bound_review(predictions, gold, review)


def test_evaluation_rejects_incomplete_whole_question_credit(tmp_path):
    predictions, gold = tmp_path / "predictions.jsonl", tmp_path / "gold.json"
    predictions.write_text(json.dumps({"record_id": "example", "questions": {"method": ["Request?"]}}) + "\n")
    gold.write_text(json.dumps({"cases": [{"record_id": "example", "questions": [
        {"question": "Request and error?", "facts": ["request", "error"]},
    ]}]}))
    review = bind_review(predictions, gold, [{"record_id": "example", "methods": {
        "method": {"whole": [[1, 1]], "facts": [[1, 1, 1]]},
    }}], reviewer="test reviewer")
    with pytest.raises(ValueError, match="lacks all required"):
        score_bound_review(predictions, gold, review)


@pytest.mark.parametrize("query,api,expected", [
    ("Can this service return 30 suggestions?", "autocomplete", ["none"]),
    ("How do I extract the locality from the response?", "reverse_geocode", ["none"]),
    ("The map only shows one route.", "directions", ["display_result"]),
    ("Some matrix elements have status NOT_FOUND.", "distance_matrix", ["matrix_input"]),
    ("The reverse geocoding request returns 422.", "reverse_geocode", ["rejected_request"]),
    ("Autocomplete never returns query predictions.", "autocomplete", ["prediction_request"]),
])
def test_decisions_require_customer_observations(query, api, expected):
    assert allowed_decisions(build_diagnostic_state({"query": query}), query, api) == expected


def test_isolated_request_question_preserves_the_reported_error():
    enquiry = {"query": "Google Directions loop returns OVER_QUERY_LIMIT."}
    state = build_diagnostic_state(enquiry)
    result = {
        "status": "final", "clarifying_questions": {"needed": False, "questions": []},
        "outputs": {"next_action": {"action_type": "answer_directly"}},
        "diagnostic_context": {"state": state.model_dump(mode="json"), "retrieved_evidence": [],
                               "interpretation": {"api": "directions"}},
    }
    client = Mock()
    client.complete.return_value = SimpleNamespace(
        finish_reason="stop", text='{"decision":"request_burst","reason":"Test a request in isolation."}',
    )
    updated = plan_staff_follow_up(result, enquiry, client=client)
    question = updated["outputs"]["clarifying_questions"]["questions"][0]["text"]
    assert "still returns OVER_QUERY_LIMIT when sent on its own" in question
    assert updated["status"] == result["status"]
    assert updated["clarifying_questions"] == result["clarifying_questions"]
    assert updated["outputs"]["next_action"] == result["outputs"]["next_action"]
