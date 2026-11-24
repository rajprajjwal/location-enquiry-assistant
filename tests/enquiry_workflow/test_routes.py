import json
from contextlib import closing
from unittest.mock import create_autospec

from copilot.enquiry_interpretation import interpret
from copilot.model_gateway.client import LLMClient
from copilot.enquiry_workflow import run_enquiry
from copilot.enquiry_workflow.cases import run_case
from copilot.case_storage import sandbox
from copilot.case_storage import cases, handlers
from copilot.case_storage.db import connect
from copilot.registered_tools.tool_registry import DocumentSearchTool
from tests.support.helpers import ScriptedClient, completion, model_json


def test_general_directions_definition_uses_official_overview():
    enquiry = {"query": "What is the direction API?"}
    response = model_json(intent="docs_how_to", api="directions", team="Support")
    interpretation = interpret(enquiry, client=ScriptedClient([completion(response)]))
    client = create_autospec(LLMClient, instance=True)
    result = run_enquiry(enquiry, interpretation, client=client)

    assert result["status"] == "final"
    assert "calculates a route" in result["response_draft"]["draft_text"]
    assert result["response_draft"]["citations"][0]["url"].startswith("https://docs.mapbox.com/")
    assert result["critic"]["verdict"] == "pass"
    client.complete.assert_not_called()


def test_pricing_compares_named_providers_with_same_monthly_workload():
    enquiry = {"query": "Compare Mapbox and Google Maps Directions for 50,000 requests per month without traffic."}
    response = model_json(intent="pricing_comparison", api="directions", team="Sales")
    interpretation = interpret(enquiry, client=ScriptedClient([completion(response)]))
    client = create_autospec(LLMClient, instance=True)
    client.complete.return_value = completion(json.dumps({
        "pricing": True,
        "items": [
            {"provider": provider, "api": "directions", "requests": 50000, "traffic": False}
            for provider in ("Mapbox", "Google Maps Platform")
        ],
    }))

    result = run_enquiry(enquiry, interpretation, client=client)

    assert result["status"] == "final", result["critic"]
    assert result["outputs"]["comparison"]["providers"] == ["Google Maps Platform", "Mapbox"]
    assert result["outputs"]["comparison"]["dimensions"] == ["pricing"]
    call, = result["tool_calls"]
    assert call["tool_name"] == "compare_providers" and call["validation_result"] == "passed"
    assert "Price summary" in result["response_draft"]["draft_text"]
    assert result["critic"]["verdict"] == "pass"
    draft = result["response_draft"]
    sources = result["pricing_source_hits"]
    assert {entry["document_id"] for entry in sources} == {
        "pricing:mapbox.directions", "pricing:google.compute_routes_essentials", "pricing:fx:2026-11-06",
    }
    for entry, citation in zip(sources, draft["citations"], strict=True):
        assert citation["url"] == entry["source_url"]
        assert citation["span"] == entry["relevant_passage"]
        assert citation["supports_claim"] == citation["span"]
        for group in entry["estimate_groups"]:
            line = next(line for line in draft["draft_text"].splitlines() if line.startswith(f"- {group}:"))
            assert f"[{entry['reference']}]" in line


def test_pricing_evidence_rejects_stale_rates(monkeypatch):
    from copilot.pricing_tools import pricing_evidence

    original = pricing_evidence._evidence_index()
    entry = original["offers"]["mapbox.directions"]
    stale = {**original, "offers": {**original["offers"], "mapbox.directions": {
        **entry, "tiers": [[100_000, 0], [500_000, 50.00]],
    }}}
    monkeypatch.setattr(pricing_evidence, "_evidence_index", lambda: stale)
    assert pricing_evidence.lookup("mapbox.directions") is None
    assert pricing_evidence.lookup("google.compute_routes_essentials")


def test_critic_rejects_related_passage_that_does_not_answer_question():
    enquiry = {"query": "How do I set waypoints in the Mapbox Directions API?"}
    response = model_json(intent="docs_how_to", sub_intent="parameter_question", api="directions", team="Support")
    interpretation = interpret(enquiry, client=ScriptedClient([completion(response)]))
    client = create_autospec(LLMClient, instance=True)
    client.complete.side_effect = lambda messages, **options: completion(
        '{"answers_enquiry": false}' if "candidate" in json.loads(messages[-1]["content"]) else '{"passage": 1}'
    )
    search = DocumentSearchTool(search_function=lambda _: [
        {"source_url": "https://example.com", "relevant_passage": "Mapbox provides traffic information."}
    ])

    result = run_enquiry(enquiry, interpretation, client=client, search=search)

    assert result["status"] == "escalated"
    assert result["step_count"] <= 10
    assert result["response_draft"] is None
    assert result["critic"]["reason"] == "The cited passage does not directly answer the enquiry."


def test_sandbox_proposal_applies_only_after_authorized_approval(tmp_path):
    client = create_autospec(LLMClient, instance=True)
    client.complete.return_value = completion(model_json(intent="docs_how_to", api="directions", team="Support"))
    with closing(connect(tmp_path / "cases.db")) as con:
        result = run_case(con, "Update sandbox ticket TKT-123. Set status to Investigating.", client=client)

        assert result["status"] == "final", result["critic"]
        action, = cases.list_pending(con, result["case_id"])
        assert action["type"] == "record_update"
        assert action["payload"]["diff"] == {"status": {"old": None, "new": "Investigating"}}
        assert sandbox.get(con, "TKT-123") == {}
        call, = result["tool_calls"]
        assert call["tool_name"] == "sandbox_record_update"
        assert call["input_validation"] == call["output_validation"] == "passed"
        stored = con.execute(
            "SELECT output_json FROM trace_steps WHERE trace_id=? AND component='tool_registry'",
            (result["trace_id"],),
        ).fetchone()
        assert json.loads(stored["output_json"]) == call

        handlers.approve_and_apply(con, action["id"], approver="deepshikha")

        assert sandbox.get(con, "TKT-123") == {"status": "Investigating"}
        assert cases.decision_log(con)[0]["final_diff"] == action["payload"]["diff"]


def test_explicit_limit_comparison_uses_provider_documents_even_if_misclassified():
    enquiry = {"query": "Compare the maximum number of coordinates for Mapbox versus Google Maps Directions."}
    response = model_json(intent="pricing_comparison", api="directions", team="Sales")
    interpretation = interpret(enquiry, client=ScriptedClient([completion(response)]))
    client = create_autospec(LLMClient, instance=True)
    client.complete.side_effect = lambda messages, **options: completion(
        '{"answers_enquiry": true}' if "candidate" in json.loads(messages[-1]["content"]) else '{"passage": 1}'
    )
    requests = []

    def search(query):
        provider = "Mapbox" if query.startswith("Mapbox") else "Google Maps Platform"
        requests.append(provider)
        return [{"source_url": f"https://example.com/{len(requests)}", "relevant_passage": f"{provider} has a coordinate limit."}]

    result = run_enquiry(enquiry, interpretation, client=client, search=DocumentSearchTool(search_function=search))

    assert result["status"] == "final", result["critic"]
    assert set(requests) == {"Mapbox", "Google Maps Platform"}
    assert result["outputs"]["comparison"]["dimensions"] == ["limits"]
    assert len(result["response_draft"]["citations"]) == 2
