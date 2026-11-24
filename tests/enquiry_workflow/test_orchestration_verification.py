from copilot.enquiry_workflow.verification.verify_orchestration import terminal_kind, looping_test
from copilot.enquiry_workflow.workflow import _result
from tests.enquiry_workflow.test_workflow import support_case


def test_delivered_clarification_is_a_completed_turn():
    enquiry, parsed = support_case()
    result = _result({
        "steps": [], "reviews": [],
        "clarification": {"field": "provider", "text": "Which map provider are you using?"},
        "terminal_reason": "Provider clarification needed.",
    }, interpretation=parsed, query=enquiry["query"])
    assert result["status"] == "clarification_needed"
    assert terminal_kind(result) == "final"


def test_empty_or_invalid_outputs_are_not_completed():
    assert terminal_kind({"status": "final", "outputs": {}, "response_draft": {}}) is None
    assert terminal_kind({"status": "escalated", "outputs": {}}) is None


def test_adversarial_loop_stops_at_ten_steps():
    report = looping_test()
    assert report["passed"]
    assert report["steps"] == 10
    assert report["critic"]["verdict"] == "needs_human"
