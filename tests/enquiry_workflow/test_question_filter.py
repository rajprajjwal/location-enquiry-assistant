import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from copilot.response_drafting.follow_up_questions import add_follow_up_questions
from copilot.response_drafting.question_filter import question_rejection


@pytest.mark.parametrize("text", [
    "Does the API documentation mention a limit on waypoints?",
    "What is the maximum number of suggestions allowed?",
    "What are the exact keys for city and country?",
    "Are you using the correct output format to retrieve distances?",
    "Is the API key still active and correctly configured?",
    "Are you required to use a specific User-Agent or can you configure one?",
    "Are you configured to send a User-Agent header?",
    "Are the coordinates in the correct format and does the API expect decimal degrees?",
])
def test_documentation_and_configuration_advice_is_suppressed(text):
    assert question_rejection(text) in {"documentation_question", "configuration_advice_as_question"}


@pytest.mark.parametrize("text", [
    "What OAuth token is being used after credential rotation?",
    "Could you share your API key?",
    "Please send your password?",
    "Could you share your access token and remove other credentials?",
    "What is the Authorization header you send?",
])
def test_credential_values_are_rejected(text):
    assert question_rejection(text) == "credential_value_requested"


@pytest.mark.parametrize("text", [
    "Could you share one failing request with your API key redacted?",
    "Could you share the exact request? Please redact your access token.",
    "What response body did you receive? Never share credentials.",
    "Could you share the request body without credentials?",
    "Does the Place Details request use the same session token?",
    "Could you share the exact failing response, including its structure?",
    "What is the scope of the access token?",
    "What quota have you configured for your project?",
    "What maximum request rate did you observe?",
    "What are the specific GPS coordinates that returned ZERO_RESULTS?",
])
def test_customer_evidence_and_safe_metadata_are_retained(text):
    assert question_rejection(text) is None


def test_rejected_credential_question_does_not_change_active_reply():
    active = {"needed": True, "questions": [{"field": "provider", "text": "Which provider?"}]}
    result = {
        "status": "clarification_needed", "clarifying_questions": active,
        "outputs": {"clarifying_questions": active,
                    "qualification_details": {}, "next_action": {"action_type": "ask_clarifying_questions"}},
    }
    client = Mock()
    client.complete.return_value = SimpleNamespace(
        finish_reason="stop",
        text=json.dumps({"questions": [{"field": "token", "text": "What OAuth token is being used?"}]}),
    )
    updated = add_follow_up_questions(result, {"query": "The call fails after credential rotation."}, client=client)
    assert updated["clarifying_questions"] == active
    assert updated["outputs"] == result["outputs"]
    assert updated["follow_up_selection"]["candidates"][0]["status"] == "credential_value_requested"
