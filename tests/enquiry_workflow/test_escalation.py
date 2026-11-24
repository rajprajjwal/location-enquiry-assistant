from dataclasses import replace
from unittest.mock import create_autospec

import pytest

from copilot.enquiry_interpretation import interpret
from copilot.enquiry_workflow import run_enquiry
from copilot.enquiry_workflow.escalation import route_enquiry
from copilot.model_gateway.client import LLMClient
from copilot.models import InterpretationOutput
from copilot.registered_tools.tool_registry import DocumentSearchTool
from copilot.response_drafting.schemas import validate_outputs
from tests.support.helpers import ScriptedClient, completion, model_json


def parsed_for(query, intent="human_handoff"):
    model = interpret({"query": query, "history": []}, client=ScriptedClient([
        completion(model_json(intent=intent, api="directions", team="Support")),
    ]))
    payload = model.model_dump(mode="json")
    payload.update(intent=intent, sub_intent=None)
    return InterpretationOutput.model_validate(payload)


def test_clear_incident_bypasses_the_model():
    query = "Production is down. Directions returns 503 for all requests."
    client = create_autospec(LLMClient, instance=True)

    route = route_enquiry(query, parsed_for(query), client=client)

    assert route["source"] == "rule"
    assert route["should_escalate"]
    assert route["owner"] == "Maps engineering"
    client.complete.assert_not_called()


def test_model_handoff_returns_schema_valid_pending_approval():
    query = "Could a human specialist help with our Directions integration?"
    client = create_autospec(LLMClient, instance=True)
    client.complete.return_value = replace(completion(
        '{"category":"advanced_support","reason":"The customer requested a specialist."}'
    ), finish_reason="stop")
    parsed = parsed_for(query)
    result = run_enquiry({"query": query, "history": []}, parsed,
                         search=DocumentSearchTool(search_function=lambda _: []), client=client)

    assert validate_outputs(result["outputs"]) == []
    assert result["outputs"]["responsible_role"] == {
        "owner": "Support L2", "team": "Support", "severity": "SEV3",
        "should_escalate": True, "reason": "The customer requested a specialist.",
    }
    assert result["outputs"]["next_action"]["approval_status"] == "pending"
    assert result["outputs"]["next_action"]["executed"] is False
    assert client.complete.call_count == 1


@pytest.mark.parametrize("output", [
    '{"category":"unregistered","reason":"Needs follow-up."}',
    '{"category":"advanced_support","reason":"  "}',
    '{"category":true,"reason":"Needs follow-up."}',
])
def test_invalid_model_choice_does_not_create_handoff(output):
    query = "Does this Directions enquiry need escalating?"
    parsed = parsed_for(query)
    client = create_autospec(LLMClient, instance=True)
    client.complete.return_value = replace(completion(output), finish_reason="stop")
    route = route_enquiry(query, parsed, client=client)

    assert not route["should_escalate"]
    assert route["source"] == "fallback"
    assert route["owner"] == "Support L1"


def test_follow_up_uses_the_earlier_workload():
    query = "Please proceed based on my earlier message."
    parsed = parsed_for(query, "pricing_comparison")
    history = [
        {"role": "user", "text": "Compare Ola and Google for 1,000,000 journeys a month in India."},
        {"role": "assistant", "text": "What driving profile do you need?"},
    ]
    route = route_enquiry(query, parsed, history=history)
    assert route["owner"] == "Account team (Sales)"
    assert not route["should_escalate"]


@pytest.mark.parametrize(("query", "intent", "owner"), [
    ("How much would the Directions API cost for 80,000 requests per month?",
     "pricing_quote", "Support L1"),
    ("Can we get traffic-aware ETAs across two markets? Compare the providers.",
     "capability_match", "Account team (Sales)"),
    ("Is per-request or session pricing cheaper for 90,000 sessions per month?",
     "pricing_comparison", "Support L1"),
    ("We need a 30×20 matrix. Which providers can do it in the fewest API calls?",
     "capability_match", "Support L1"),
])
def test_routine_owner_uses_the_customer_decision(query, intent, owner):
    client = create_autospec(LLMClient, instance=True)
    route = route_enquiry(query, parsed_for(query, intent), client=client)
    assert route["owner"] == owner
    assert not route["should_escalate"]
    client.complete.assert_not_called()


def test_currency_reply_preserves_the_earlier_commercial_request():
    query = "USD only, please."
    parsed = parsed_for(query, "pricing_quote")
    history = [
        {"role": "user", "text": "Which is cheaper for 70,000 requests per month, Mapbox Directions or Google Maps?"},
        {"role": "assistant", "text": "Which currency should I use?"},
    ]
    route = route_enquiry(query, parsed, history=history)
    assert route["owner"] == "Account team (Sales)"
    assert not route["should_escalate"]


@pytest.mark.parametrize(("query", "intent", "owner"), [
    ("What does Mapbox Directions cost for 600,000 requests per month?",
     "pricing_quote", "Support L1"),
    ("Google Route Matrix for two-wheelers in India, 90,000 elements a month. Cost?",
     "pricing_quote", "Support L1"),
    ("Compare Google Maps and Mapbox pricing for 600,000 Directions requests per month.",
     "pricing_comparison", "Account team (Sales)"),
    ("Is Google Routes API pricing lower for the standard or advanced SKU?",
     "pricing_comparison", "Support L1"),
    ("We need 60,000 reverse geocodes per month in Canada. Options and estimated cost?",
     "pricing_comparison", "Account team (Sales)"),
    ("For our billing audit, how much does Google bill when a session ends with Place Details?",
     "pricing_quote", "Support L1"),
    ("Which provider should we choose for a routing service under our budget?",
     "capability_match", "Account team (Sales)"),
    ("Can we get a custom quote for Mapbox Directions for our company?",
     "pricing_quote", "Account team (Sales)"),
    ("We were charged twice. Can you review our invoice for Google Maps?",
     "pricing_quote", "Account team (Sales)"),
])
def test_public_pricing_ownership_boundary(query, intent, owner):
    client = create_autospec(LLMClient, instance=True)
    route = route_enquiry(query, parsed_for(query, intent), client=client)
    assert route["owner"] == owner
    assert not route["should_escalate"]
    client.complete.assert_not_called()



def test_currency_reply_preserves_a_single_provider_public_estimate():
    query = "Just USD, please."
    history = [{"role": "user", "text": "How much would Google Routes cost for 900,000 requests per month?"}]
    route = route_enquiry(query, parsed_for(query, "pricing_quote"), history=history)
    assert route["owner"] == "Support L1"
    assert not route["should_escalate"]



@pytest.mark.parametrize(("query", "intent", "owner"), [
    ("We need a matrix of 40 origins and 20 destinations. Which providers accept this in a single call?",
     "capability_match", "Support L1"),
    ("A prospect is evaluating a matrix service. What licensing and intended use should we confirm before recommending a provider, including pricing?",
     "sales_qualification", "Account team (Sales)"),
    ("Does our existing matrix integration accept 20 origins in one request?",
     "docs_how_to", "Support L1"),
])
def test_ownership_distinguishes_capacity_from_deployment_qualification(query, intent, owner):
    client = create_autospec(LLMClient, instance=True)
    route = route_enquiry(query, parsed_for(query, intent), client=client)
    assert route["owner"] == owner
    assert not route["should_escalate"]
    client.complete.assert_not_called()



@pytest.mark.parametrize(("query", "intent", "owner"), [
    ("We already use Mapbox. What would 500,000 directions calls cost?", "pricing_quote", "Support L1"),
    ("We are a new customer. What would 500,000 directions calls cost?", "pricing_quote", "Account team (Sales)"),
    ("We are using a routing service. Compare providers for our coverage question.", "coverage_limits", "Support L1"),
    ("A prospect needs documentation for reverse geocoding.", "docs_how_to", "Account team (Sales)"),
    ("Our existing integration needs guidance on licensing restrictions.", "docs_how_to", "Support L1"),
])
def test_customer_status_controls_routine_ownership(query, intent, owner):
    route = route_enquiry(query, parsed_for(query, intent))
    assert route["owner"] == owner
    assert not route["should_escalate"]


def test_unknown_customer_status_requires_evidence():
    from copilot.safety.escalation_policy import customer_status
    assert customer_status("What is Google Directions pricing?") == "unknown"
    assert customer_status("Which provider should I choose?") == "unknown"


def test_reported_address_quality_uses_support_triage():
    query = "The API returns the wrong address."
    route = route_enquiry(query, parsed_for(query, "human_handoff"))
    assert route["owner"] == "Support L2"
    assert route["should_escalate"]


def test_billing_policy_handoff_uses_sales():
    query = "Please prepare a handoff to a human billing reviewer about prepaid credits."
    client = create_autospec(LLMClient, instance=True)
    client.complete.return_value = replace(completion(
        '{"category":"advanced_support","reason":"A human billing review is requested."}'
    ), finish_reason="stop")
    route = route_enquiry(query, parsed_for(query), client=client)
    assert route["owner"] == "Account team (Sales)"
    assert route["should_escalate"]



@pytest.mark.parametrize("query", [
    "Which routing APIs could we use?",
    "Can we use this service for our planned launch?",
    "Should we use Google Maps or Mapbox?",
])
def test_provider_selection_does_not_establish_existing_customer(query):
    from copilot.safety.escalation_policy import customer_status
    assert customer_status(query) == "unknown"


@pytest.mark.parametrize(("query", "owner"), [
    ("Our drivers need Urdu instructions. Which routing APIs support that?", "Account team (Sales)"),
    ("We run refrigerated trucks. Which routing APIs support truck restrictions?", "Account team (Sales)"),
    ("Our riders need addresses in two countries. Who covers both?", "Account team (Sales)"),
    ("We are an existing customer. Our drivers need Urdu instructions. Which routing APIs support that?", "Support L1"),
    ("We need a 40 by 10 matrix. Which providers can handle that in one call?", "Support L1"),
])
def test_business_requirement_discovery_is_provisional(query, owner):
    route = route_enquiry(query, parsed_for(query, "capability_match"))
    assert route["owner"] == owner
    assert not route["should_escalate"]
    if "existing customer" not in query:
        assert route["ownership_review"]["customer_status"] == "unknown"
        assert route["ownership_review"]["provisional"]


@pytest.mark.parametrize(("status", "owner"), [
    (None, "Account team (Sales)"),
    ("existing", "Support L1"),
])
def test_generic_feature_discovery_follows_the_confirmed_relationship_policy(status, owner):
    query = "Which matrix APIs return a precision indicator?"
    route = route_enquiry(query, parsed_for(query, "capability_match"), confirmed_customer_status=status)
    assert route["owner"] == owner
    assert route["ownership_review"]["customer_status"] == (status or "unknown")
