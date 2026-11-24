from contextlib import closing
from unittest.mock import create_autospec

import pytest

from copilot.enquiry_workflow import run_enquiry
from copilot.enquiry_workflow.escalation import route_enquiry
from copilot.model_gateway.client import LLMClient
from copilot.registered_tools.tool_registry import DocumentSearchTool
from copilot.response_drafting.schemas import validate_outputs
from tests.enquiry_workflow.test_escalation import parsed_for


def test_unknown_status_has_a_provisional_owner_and_reason():
    query = "How do I set waypoints in Mapbox Directions?"
    route = route_enquiry(query, parsed_for(query, "docs_how_to"))
    review = route["ownership_review"]
    assert review["customer_status"] == "unknown"
    assert review["provisional"] and review["confirmation_needed"]
    assert not review["status_deferred"]
    assert review["suggested_question"]
    assert "Provisional owner" in route["reason"]
    assert route["owner"] in route["reason"]


@pytest.mark.parametrize("reply", [
    "Not sure. Answer with the details from my first message and note where that choice would change things.",
    "Let's leave that open for now; answer based on my earlier message.",
])
def test_explicit_status_deferral_does_not_repeat_the_question(reply):
    history = [
        {"role": "user", "text": "Quote Google Maps routing for 600,000 requests a month."},
        {"role": "assistant", "text": "Is this a new or existing Google Cloud project?"},
    ]
    route = route_enquiry(reply, parsed_for(reply, "pricing_quote"), history=history)
    review = route["ownership_review"]
    assert review["customer_status"] == "unknown"
    assert review["provisional"] and review["status_deferred"]
    assert review["suggested_question"] is None
    assert not route["should_escalate"]


def test_deferral_is_retained_across_a_later_currency_reply():
    history = [
        {"role": "user", "text": "Quote the routing API for 600,000 calls a month."},
        {"role": "assistant", "text": "Are you a new or existing customer?"},
        {"role": "user", "text": "Let's leave that open for now."},
        {"role": "assistant", "text": "Which currency should I use?"},
    ]
    route = route_enquiry("USD, please.", parsed_for("USD, please.", "pricing_quote"), history=history)
    assert route["ownership_review"]["status_deferred"]
    assert route["ownership_review"]["suggested_question"] is None


def test_explicit_status_resolves_the_deferral():
    history = [
        {"role": "assistant", "text": "Are you a new or existing customer?"},
        {"role": "user", "text": "Let's leave that open for now."},
    ]
    query = "We are an existing customer. Please use USD."
    review = route_enquiry(query, parsed_for(query, "pricing_quote"), history=history)["ownership_review"]
    assert review["customer_status"] == "existing"
    assert not review["provisional"]
    assert not review["status_deferred"]
    assert not review["confirmation_needed"]


def test_deferring_an_unrelated_fact_does_not_defer_status():
    history = [{"role": "assistant", "text": "Which currency should I use?"}]
    query = "Not sure. Answer based on my first message."
    review = route_enquiry(query, parsed_for(query, "pricing_quote"), history=history)["ownership_review"]
    assert not review["status_deferred"]


def test_formal_handoff_owner_does_not_depend_on_unknown_status():
    query = "Production is down. Directions returns 503 for all requests."
    route = route_enquiry(query, parsed_for(query, "troubleshooting"))
    assert route["should_escalate"]
    assert not route["ownership_review"]["provisional"]
    assert route["ownership_review"]["suggested_question"] is None


def test_provisional_ownership_is_returned_through_the_workflow():
    query = "How do I set waypoints in Mapbox Directions?"
    parsed = parsed_for(query, "docs_how_to")
    client = create_autospec(LLMClient, instance=True)
    from tests.support.helpers import completion
    client.complete.return_value = completion('{"passage":1,"answers_enquiry":true}')
    search = DocumentSearchTool(search_function=lambda _: [
        {"source_url": "https://example.com/waypoints", "relevant_passage": "Add intermediate locations in the waypoints field."}
    ])
    result = run_enquiry({"query": query, "history": []}, parsed, client=client, search=search)
    assert result["ownership_review"]["provisional"]
    assert "Provisional owner" in result["outputs"]["responsible_role"]["reason"]
    assert validate_outputs(result["outputs"]) == []


def test_provisional_metadata_survives_reopening_a_case(tmp_path, monkeypatch):
    from copilot.enquiry_workflow import cases as service
    from copilot.case_storage import cases
    from copilot.case_storage.db import connect
    query = "How do I set waypoints in Directions?"
    parsed = parsed_for(query, "docs_how_to")
    monkeypatch.setattr(service, "interpret", lambda *args, **kwargs: parsed)
    monkeypatch.setattr(service, "add_follow_up_questions", lambda result, *args, **kwargs: result)
    db = tmp_path / "cases.db"
    with closing(connect(db)) as con:
        result = service.run_case(con, query, search=DocumentSearchTool(documents=[]))
    with closing(connect(db)) as con:
        restored = cases.load_state(con, result["case_id"])["last_result"]
        assert restored["ownership_review"] == result["ownership_review"]
        assert restored["ownership_review"]["provisional"]
        assert restored["status"] == result["status"]



def test_known_customer_status_survives_a_short_follow_up():
    history = [
        {"role": "user", "text": "We are an existing customer."},
        {"role": "assistant", "text": "Which currency should I use?"},
    ]
    query = "USD, please."
    review = route_enquiry(query, parsed_for(query, "pricing_quote"), history=history)["ownership_review"]
    assert review["customer_status"] == "existing"
    assert not review["provisional"]
    assert review["suggested_question"] is None



def test_new_customer_follow_up_keeps_sales_ownership():
    history = [
        {"role": "user", "text": "We are a new customer."},
        {"role": "assistant", "text": "Which currency should I use?"},
    ]
    query = "USD, please."
    route = route_enquiry(query, parsed_for(query, "pricing_quote"), history=history)
    assert route["owner"] == "Account team (Sales)"
    assert route["ownership_review"]["customer_status"] == "new"
    assert not route["ownership_review"]["provisional"]
