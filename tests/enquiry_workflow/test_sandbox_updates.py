from contextlib import closing
from types import SimpleNamespace
from unittest.mock import create_autospec

from copilot.case_storage import cases, sandbox
from copilot.case_storage.db import connect
from copilot.enquiry_workflow.cases import run_case
from copilot.enquiry_workflow.sandbox_updates import update_request
from copilot.model_gateway.client import LLMClient
from copilot.registered_tools.tool_registry import DocumentSearchTool
from tests.support.helpers import completion, model_json


def _interpretation(api, intent, sub_intent):
    return SimpleNamespace(api=api, intent=intent, sub_intent=sub_intent,
                           qualification_details=SimpleNamespace(current_provider=None))


def test_opportunity_uses_quote_fields_and_preserves_provider_order():
    request = update_request(
        "Compare Ola Maps vs Google Places prices and propose an update for OPP-123.",
        _interpretation("autocomplete", "pricing_comparison", "pricing_comparison"),
        {"owner": "Account team (Sales)", "severity": "SEV4"},
        comparison={"dimensions": ["pricing"]}, answer_ready=True,
    )
    assert request["fields"] == {
        "api": "autocomplete", "owner": "Account team (Sales)",
        "providers": "Ola Maps, Google Maps Platform", "stage": "quote_drafted",
        "next_step": "send reviewed answer to customer",
    }


def test_ticket_uses_sub_intent_and_actual_severity():
    request = update_request(
        "Propose an update to TKT-123 for the malformed Mapbox Directions response.",
        _interpretation("directions", "troubleshooting", "error_resolution"),
        {"owner": "Support L2", "severity": "SEV3"}, answer_ready=True,
    )
    assert request["fields"] == {
        "api": "directions", "owner": "Support L2", "providers": "Mapbox",
        "category": "error_resolution", "severity": "SEV3", "status": "solution_proposed",
    }


def test_manual_review_can_queue_known_fields_without_claiming_a_solution(tmp_path):
    client = create_autospec(LLMClient, instance=True)
    client.complete.return_value = completion(model_json(
        intent="docs_how_to", api="directions", team="Support", sub_intent="integration_question",
    ))
    search = DocumentSearchTool(search_function=lambda _: [])
    with closing(connect(tmp_path / "cases.db")) as con:
        outcome = run_case(con,
                           'Sandbox ticket TKT-123. Customer wrote: "How do we integrate Mapbox Directions?" '
                           "Draft a reply and propose ticket updates.",
                           client=client, search=search)
        assert outcome["status"] == "escalated"
        assert outcome["outputs"]["next_action"]["action_type"] == "refuse"
        action, = cases.list_pending(con, outcome["case_id"])
        assert action["status"] == "pending"
        assert set(action["payload"]["fields"]) == {"api", "category", "owner", "providers", "severity"}
        assert action["payload"]["diff"]["providers"] == {"old": None, "new": "Mapbox"}
        assert not sandbox.get(con, "TKT-123")
        assert outcome["step_count"] <= 10
