from contextlib import closing
from copy import deepcopy
from unittest.mock import patch

import pytest

from copilot.enquiry_workflow.escalation import route_enquiry
from copilot.safety import escalation_policy
from tests.enquiry_workflow.test_escalation import parsed_for


@pytest.mark.parametrize(("query", "status"), [
    ("Our mobile app calls Nominatim reverse every 20 seconds.", "existing"),
    ("Our application uses Google Directions.", "existing"),
    ("Our app will call Nominatim reverse.", "unknown"),
    ("Our app does not call Nominatim reverse.", "unknown"),
    ("If our app calls Nominatim reverse, is that allowed?", "unknown"),
    ("Our app used to call Nominatim reverse.", "unknown"),
    ("How many times can our app call Nominatim reverse?", "unknown"),
])
def test_actual_use_is_evidence_based(query, status):
    policy = {**escalation_policy.policy(), "actual_use_detection": True}
    with patch.object(escalation_policy, "policy", return_value=policy):
        assert escalation_policy.customer_status(query) == status


def test_quoted_customer_actual_use_routes_to_support():
    query = 'Sandbox CRM ticket TKT-12. Customer wrote: "Our mobile app calls Google Directions every minute." Draft a reply.'
    policy = {**escalation_policy.policy(), "actual_use_detection": True}
    with patch.object(escalation_policy, "policy", return_value=policy):
        result = route_enquiry(query, parsed_for(query, "sales_qualification"))
    assert result["owner"] == "Support L1"
    assert result["ownership_review"]["customer_status"] == "existing"


@pytest.mark.parametrize(("query", "intent", "owner"), [
    ("Which providers return language-specific address suggestions?", "capability_match", "Account team (Sales)"),
    ("We are an existing customer. Which providers support our API coverage?", "coverage_limits", "Support L1"),
    ("Which providers accept a 40 by 20 matrix in one call?", "coverage_limits", "Support L1"),
])
def test_provider_discovery_respects_status_and_limits(query, intent, owner):
    policy = {**escalation_policy.policy(), "provider_discovery_fallback": True}
    with patch.object(escalation_policy, "policy", return_value=policy):
        result = route_enquiry(query, parsed_for(query, intent))
    assert result["owner"] == owner


@pytest.mark.parametrize(("status", "owner"), [
    ("existing", "Support L1"),
    ("new", "Account team (Sales)"),
])
def test_case_record_status_controls_the_normal_workflow(tmp_path, monkeypatch, status, owner):
    from copilot.enquiry_workflow import cases as service
    from copilot.case_storage import cases
    from copilot.case_storage.db import connect
    from copilot.registered_tools.tool_registry import DocumentSearchTool
    query = "How do I set waypoints in Directions?"
    parsed = parsed_for(query, "docs_how_to")
    monkeypatch.setattr(service, "interpret", lambda *args, **kwargs: parsed)
    monkeypatch.setattr(service, "add_follow_up_questions", lambda result, *args, **kwargs: result)
    db = tmp_path / "cases.db"
    with closing(connect(db)) as con:
        case_id = cases.create_case(con)
        cases.set_fact(con, case_id, "customer_status", status)
    with closing(connect(db)) as con:
        result = service.run_case(con, query, case_id=case_id, search=DocumentSearchTool(documents=[]))
        assert result["outputs"]["responsible_role"]["owner"] == owner
        assert result["ownership_review"]["customer_status"] == status
        assert not result["ownership_review"]["provisional"]
        assert cases.load_state(con, case_id)["last_result"]["ownership_review"] == result["ownership_review"]


@pytest.mark.parametrize(("reply", "owner"), [
    ("Existing", "Support L1"),
    ("New", "Account team (Sales)"),
])
def test_short_status_follow_up_resolves_ownership(reply, owner):
    history = [{"role": "assistant", "text": "Are you a new or existing customer?"}]
    result = route_enquiry(reply, parsed_for(reply, "pricing_quote"), history=history)
    assert result["owner"] == owner
    assert not result["ownership_review"]["provisional"]


def test_explicit_current_reply_can_correct_a_case_fact():
    history = [{"role": "assistant", "text": "Are you a new or existing customer?"}]
    result = route_enquiry("New", parsed_for("New", "pricing_quote"), history=history,
                           confirmed_customer_status="existing")
    assert result["ownership_review"]["customer_status"] == "new"
    assert result["owner"] == "Account team (Sales)"


def test_unverified_customer_status_value_is_rejected():
    with pytest.raises(ValueError, match="Confirmed customer status"):
        route_enquiry("What does the service cost?", parsed_for("What does the service cost?", "pricing_quote"),
                      confirmed_customer_status="probably existing")
