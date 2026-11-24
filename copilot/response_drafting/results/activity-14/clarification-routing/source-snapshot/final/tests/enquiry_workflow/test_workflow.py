import json
from unittest.mock import create_autospec

from copilot.enquiry_interpretation import interpret
from copilot.model_gateway.client import LLMClient
from copilot.enquiry_workflow import run_enquiry, workflow
from copilot.registered_tools.tool_registry import DocumentSearchTool
from copilot.response_drafting.schemas import validate_outputs
from tests.support.helpers import ScriptedClient, completion, model_json


def support_case(provider="Mapbox"):
    api = f"{provider} Directions API" if provider else "Directions API"
    enquiry = {"query": f"How do I set waypoints in the {api}?", "history": []}
    reply = model_json(
        intent="docs_how_to", sub_intent="parameter_question", api="directions", team="Support"
    )
    return enquiry, interpret(enquiry, client=ScriptedClient([completion(reply)]))


def test_support_enquiry_returns_a_grounded_draft():
    enquiry, interpretation = support_case()
    passage = "Add intermediate locations in the waypoints field."
    source = "https://example.com/directions"
    search = DocumentSearchTool(search_function=lambda query: [
        {"source_url": source, "relevant_passage": passage}
    ])
    client = create_autospec(LLMClient, instance=True)
    client.complete.return_value = completion('{"passage": 1, "answers_enquiry": true}')
    result = run_enquiry(enquiry, interpretation, search=search, client=client)
    assert client.complete.call_args.kwargs["response_format"] == {"type": "json_object"}

    assert result["status"] == "final"
    assert result["response_draft"]["draft_text"] == passage
    assert result["response_draft"]["citations"][0]["url"] == source
    assert [step["action"] for step in result["steps"]] == [
        "plan", "document_search", "draft", "critic"
    ]
    assert result["step_count"] == 4
    assert result["critic"]["verdict"] == "pass"
    assert result["proposed_actions"] == []


def test_repeated_critic_revisions_stop_at_the_step_limit(monkeypatch):
    planned = (f"retry {index}" for index in range(4))
    monkeypatch.setattr(workflow, "_plan", lambda *args: next(planned))
    enquiry, interpretation = support_case()
    searches = []

    def search(query):
        searches.append(query)
        return [{"source_url": "https://example.com", "relevant_passage": "Unrelated."}]

    client = create_autospec(LLMClient, instance=True)
    client.complete.return_value = completion('{"passage": null}')
    result = run_enquiry(
        enquiry, interpretation, search=DocumentSearchTool(search_function=search), client=client
    )

    assert result["status"] == "escalated"
    assert result["step_count"] == 10
    assert result["response_draft"] is None
    assert result["critic"]["verdict"] == "needs_human"
    assert result["critic"]["reason"] == "Step limit reached."
    assert result["critic"]["reviews"]
    assert validate_outputs(result["outputs"]) == []
    assert result["outputs"]["response_draft"]["is_refusal"]
    assert result["outputs"]["next_action"]["action_type"] == "refuse"
    assert result["proposed_actions"] == []
    assert searches == ["retry 0", "retry 1", "retry 2"]


def test_tool_failure_is_counted_and_records_why_the_critic_did_not_run():
    enquiry, interpretation = support_case()

    def search(query):
        raise RuntimeError("Search unavailable")

    result = run_enquiry(enquiry, interpretation, search=DocumentSearchTool(search_function=search))

    assert result["status"] == "escalated"
    assert result["step_count"] == 2
    assert result["steps"][-1]["status"] == "failed"
    assert result["critic"]["verdict"] == "not_run"


def test_real_corpus_retrieval_feeds_cited_support_draft():
    from copilot.enquiry_workflow.retrieval import rag_document_search

    enquiry, interpretation = support_case()
    client = create_autospec(LLMClient, instance=True)
    def select_waypoint_passage(messages, **options):
        payload = json.loads(messages[-1]["content"])
        if "candidate" in payload:
            return completion('{"answers_enquiry": true}')
        passages = payload["passages"]
        index = next(
            i for i, row in enumerate(passages, 1) if "waypoint" in row["relevant_passage"].lower()
        )
        return completion(json.dumps({"passage": index}))

    client.complete.side_effect = select_waypoint_passage
    result = run_enquiry(
        enquiry, interpretation,
        search=rag_document_search(mode="bm25", rerank=False), client=client,
    )

    assert result["status"] == "final"
    citation = result["response_draft"]["citations"][0]
    assert citation["url"].startswith("https://")
    assert "waypoint" in citation["span"].lower()
    assert result["critic"]["verdict"] == "pass"


def test_production_incident_gathers_evidence_and_preserves_escalation():
    enquiry = {"query": "Production is down. Directions returns 503 for all requests."}
    reply = model_json(
        intent="troubleshooting", sub_intent="production_incident",
        api="directions", team="Support",
    )
    interpretation = interpret(enquiry, client=ScriptedClient([completion(reply)]))
    client = create_autospec(LLMClient, instance=True)
    search = DocumentSearchTool(search_function=lambda _: [
        {"source_url": "https://example.com/errors", "relevant_passage": "503 Service Unavailable."},
    ])
    result = run_enquiry(enquiry, interpretation, search=search, client=client)

    assert result["status"] == "escalated"
    assert result["step_count"] == 2
    assert result["response_draft"] is None
    assert result["proposed_actions"] == [{
        "action_type": "propose_escalation",
        "description": "Ask a reviewer to approve handoff to Maps engineering.",
        "requires_human_approval": True,
        "approval_status": "pending",
        "executed": False,
        "escalation": {
            "severity": "SEV1", "owner": "Maps engineering",
            "summary": "Escalation rule matched production incident.",
        },
    }]
    client.complete.assert_not_called()
    assert validate_outputs(result["outputs"]) == []
    assert result["outputs"]["next_action"] == result["proposed_actions"][0]
    assert result["outputs"]["responsible_role"]["owner"] == "Maps engineering"
    assert result["outputs"]["responsible_role"]["severity"] == "SEV1"
    assert [call["tool_name"] for call in result["tool_calls"]] == ["document_search"]
    assert result["route_evidence"]["retrieved_passages"] == [
        {"url": "https://example.com/errors", "span": "503 Service Unavailable."},
    ]

    def unavailable(_query):
        raise RuntimeError("Index unavailable")

    failed = run_enquiry(enquiry, interpretation,
                         search=DocumentSearchTool(search_function=unavailable), client=client)
    assert failed["status"] == "escalated"
    assert failed["proposed_actions"] == result["proposed_actions"]
    assert failed["tool_calls"][0]["execution_status"] == "error"



def test_invalid_selection_can_repair_to_unsupported_then_use_focused_search():
    from copilot.enquiry_workflow.retrieval import rag_document_search

    enquiry, interpretation = support_case("Google Maps Platform")
    client = create_autospec(LLMClient, instance=True)

    def reply(messages, **options):
        payload = json.loads(messages[-1]["content"])
        if "candidate" in payload:
            return completion('{"answers_enquiry": true}')
        if payload["feedback"] is None:
            return completion('{"passage": 7}')
        if payload.get("selection_repair"):
            assert "outside the returned list of 5" in payload["feedback"]
            return completion('{"passages": [], "retry_query": "Google Directions waypoints get-directions"}')
        assert "found no passage" in payload["feedback"]
        source = next(
            row for row in payload["passages"]
            if "developers.google.com/maps/documentation/directions/get-directions" in row["source_url"]
            and "waypoint" in row["relevant_passage"].lower()
        )
        return completion(json.dumps({"passage": source["passage_id"]}))

    client.complete.side_effect = reply
    result = run_enquiry(
        enquiry, interpretation, search=rag_document_search(mode="bm25", rerank=False), client=client,
    )

    assert result["status"] == "final"
    assert result["step_count"] == 8
    assert result["critic"]["reviews"][0]["verdict"] == "revise"
    assert result["critic"]["verdict"] == "pass"


def test_no_useful_passage_reports_the_reason_before_the_step_limit():
    enquiry, interpretation = support_case()
    client = create_autospec(LLMClient, instance=True)
    client.complete.return_value = completion('{"passage": null}')
    result = run_enquiry(
        enquiry, interpretation,
        search=DocumentSearchTool(search_function=lambda query: [
            {"source_url": "https://example.com", "relevant_passage": "Unrelated."}
        ]),
        client=client,
    )

    assert result["status"] == "escalated"
    assert result["step_count"] < 10
    assert result["critic"]["reason"] == "The model found no passage that answered the enquiry."
    assert client.complete.call_count == 2



def test_waypoint_question_asks_for_provider_before_searching():
    enquiry, interpretation = support_case(None)
    client = create_autospec(LLMClient, instance=True)
    search = create_autospec(DocumentSearchTool, instance=True)
    result = run_enquiry(enquiry, interpretation, search=search, client=client)

    assert result["status"] == "clarification_needed"
    assert result["clarifying_questions"]["questions"] == [
        {"field": "provider", "text": "Which map provider are you using?"}
    ]
    assert result["step_count"] == 1
    assert result["response_draft"] is None
    assert validate_outputs(result["outputs"]) == []
    assert result["outputs"]["clarifying_questions"] == result["clarifying_questions"]
    assert result["outputs"]["next_action"]["action_type"] == "ask_clarifying_questions"
    search.tool_definition.return_value.executor.assert_not_called()
    client.complete.assert_not_called()


def test_prior_user_turn_supplies_provider():
    enquiry, interpretation = support_case(None)
    enquiry["history"] = [{"role": "user", "text": "We use Mapbox."}]
    searches = []
    client = create_autospec(LLMClient, instance=True)
    client.complete.return_value = completion('{"passage": 1, "answers_enquiry": true}')

    def search(query):
        searches.append(query)
        return [{"source_url": "https://example.com/mapbox", "relevant_passage": "Use a waypoint."}]

    result = run_enquiry(
        enquiry, interpretation, search=DocumentSearchTool(search_function=search), client=client,
    )
    assert result["status"] == "final"
    assert "Provider: Mapbox." in searches[0]


def test_hybrid_setup_failure_reaches_the_critic_result(monkeypatch):
    from copilot.enquiry_workflow import retrieval

    enquiry, interpretation = support_case()
    client = create_autospec(LLMClient, instance=True)
    monkeypatch.setattr(retrieval, "retrieval_setup_issues", lambda *args, **kwargs: ["Build the dense index."])

    result = run_enquiry(enquiry, interpretation, client=client)

    assert result["status"] == "escalated"
    assert result["critic"]["reason"] == "Hybrid retrieval is unavailable. Build the dense index."
    client.complete.assert_not_called()
