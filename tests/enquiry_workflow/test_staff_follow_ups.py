from unittest.mock import Mock
import json
from types import SimpleNamespace
import pytest

from copilot.response_drafting.follow_up_questions import add_follow_up_questions


def result_for(api, active=None):
    block = {"needed": bool(active), "questions": [active] if active else []}
    return {
        "status": "clarification_needed" if active else "final",
        "clarifying_questions": block,
        "outputs": {
            "next_action": {"action_type": "ask_clarifying_questions" if active else "answer_directly"},
            "qualification_details": {"use_case_api": {"api": api}},
            "clarifying_questions": block,
        },
    }


def test_batch_rate_and_size_become_a_single_staff_question():
    result = result_for("reverse_geocode")
    client = Mock()
    updated = add_follow_up_questions(
        result, {"query": "Mapbox reverse geocoding batch returns HTTP 429."}, client=client,
    )
    questions = updated["outputs"]["clarifying_questions"]["questions"]
    assert len(questions) == 1
    assert "requests per minute" in questions[0]["text"]
    assert "coordinates were in a typical batch" in questions[0]["text"]
    assert updated["clarifying_questions"] == result["clarifying_questions"]
    assert updated["outputs"]["next_action"] == result["outputs"]["next_action"]
    client.complete.assert_not_called()


def test_batch_question_omits_a_rate_the_customer_already_supplied():
    result = result_for("reverse_geocode")
    updated = add_follow_up_questions(result, {
        "query": "Reverse geocoding batch returns 429. We send 120 batch requests per minute.",
    })
    assert updated["outputs"]["clarifying_questions"]["questions"] == [{
        "field": "batch_limit", "text": "Can you share the number of coordinates in a typical batch?",
    }]


def test_staff_follow_up_does_not_replace_the_pending_question():
    active = {"field": "provider", "text": "Which map provider are you using?"}
    result = result_for("autocomplete", active)
    updated = add_follow_up_questions(result, {"query": "Autocomplete returns 429 during a promotion."})
    assert updated["clarifying_questions"] == result["clarifying_questions"]
    assert updated["outputs"]["clarifying_questions"]["questions"][0] == active
    assert updated["outputs"]["clarifying_questions"]["questions"][1]["field"] == "peak_rate"


def test_declined_history_does_not_generate_an_extra_question():
    result = result_for("directions")
    updated = add_follow_up_questions(result, {
        "query": "Not sure. Please proceed with what we know.",
        "history": [{"role": "user", "text": "Directions returns 429."},
                    {"role": "assistant", "text": "What was the peak request rate?"}],
    })
    assert updated["outputs"]["clarifying_questions"]["questions"] == []


@pytest.mark.parametrize("action", ["answer_directly", "propose_record_update", "propose_escalation"])
def test_unmatched_diagnosis_reaches_model_for_each_route(action):
    result = result_for("directions")
    result["outputs"]["next_action"]["action_type"] = action
    candidate = {
        "field": "request_example", "facts": ["request_example"],
        "decision_impact": "Identify whether the client submitted a malformed request.",
        "evidence": "The routing call fails.",
        "text": "Could you share one failing request? Please remove credentials.",
    }
    client = Mock()
    client.complete.return_value = SimpleNamespace(
        finish_reason="stop", text=json.dumps({"questions": [candidate]}),
    )
    updated = add_follow_up_questions(result, {"query": "The routing call fails."}, client=client)
    assert updated["outputs"]["clarifying_questions"]["questions"] == [
        {"field": candidate["field"], "text": candidate["text"]},
    ]
    assert updated["clarifying_questions"] == result["clarifying_questions"]
    assert updated["outputs"]["next_action"] == result["outputs"]["next_action"]
    assert updated["follow_up_selection"]["status"] == "model_selected"


def test_unsupported_fact_selection_is_visible_in_diagnostics():
    client = Mock()
    client.complete.return_value = SimpleNamespace(
        finish_reason="stop",
        text=json.dumps({"questions": [{
            "field": "request_example", "facts": ["request_example"],
            "decision_impact": "Reproduce the error.", "evidence": "Invented customer text",
            "text": "Could you share a failing request?",
        }]}),
    )
    updated = add_follow_up_questions(result_for("directions"), {"query": "A route failed."}, client=client)
    assert updated["outputs"]["clarifying_questions"]["questions"] == []
    assert updated["follow_up_selection"]["candidates"][0]["status"] == "unsupported_missing_facts"
