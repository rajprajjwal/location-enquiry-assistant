import json
from contextlib import closing
from unittest.mock import create_autospec

from copilot.model_gateway.client import LLMClient
from copilot.enquiry_workflow import workflow
from copilot.enquiry_workflow.cases import run_case
from copilot.enquiry_workflow.coverage_evidence import _google_table
from copilot.enquiry_workflow.combined_comparison import compare_prices, monthly_workload
from copilot.response_drafting.schemas import validate_outputs
from copilot.case_storage import cases
from copilot.case_storage.db import connect
from copilot.registered_tools.tool_registry import DocumentSearchTool
from tests.support.helpers import completion, model_json

_PROVIDERS = ("Google Maps Platform", "Mapbox", "Mappls (MapmyIndia)")
_QUERY = "Compare cost, limits, and coverage in India for Google Maps and Mapbox Directions at 150,000 requests per month without traffic."
_DOCS = {
    ("Google Maps Platform", "limits"): (
        "https://developers.google.com/maps/documentation/routes/usage-and-billing",
        "For this test fixture, Google Routes accepts up to 25 intermediate waypoints.",
    ),
    ("Google Maps Platform", "coverage"): (
        "https://developers.google.com/maps/coverage",
        "For this test fixture, Google documents Directions coverage for India.",
    ),
    ("Mapbox", "limits"): (
        "https://docs.mapbox.com/api/navigation/directions/",
        "For this test fixture, Mapbox Directions accepts a maximum of 25 coordinates.",
    ),
    ("Mapbox", "coverage"): (
        "https://docs.mapbox.com/help/dive-deeper/directions/",
        "For this test fixture, Mapbox Directions driving coverage includes India.",
    ),
    ("Mappls (MapmyIndia)", "limits"): (
        "https://developer.mappls.com/documentation/sdk/rest-apis/mappls-routing-api/readme",
        "For this test fixture, Mappls Directions accepts up to 20 waypoints.",
    ),
}


def _client():
    client = create_autospec(LLMClient, instance=True)

    def respond(messages, **options):
        try:
            payload = json.loads(messages[-1]["content"])
        except ValueError:
            payload = {}
        if isinstance(payload, dict) and "passages" in payload:
            return completion('{"passage": 1}')
        if isinstance(payload, dict) and "candidate" in payload:
            return completion('{"answers_enquiry": true}')
        return completion(model_json(intent="pricing_comparison", sub_intent="pricing_comparison",
                                     api="directions", team="Sales"))

    client.complete.side_effect = respond
    return client


def _search(calls, missing=(), generic=()):
    def search(query):
        provider, rest = query.split(": ", 1)
        dimension = "coverage" if "geographic coverage" in rest.split("?", 1)[0] else "limits"
        calls.append((provider, dimension, rest))
        if (provider, dimension) in missing:
            # A passage from the other provider must never qualify as a substitute.
            url, text = _DOCS[("Google Maps Platform", "coverage")]
        elif (provider, dimension) in generic:
            url = _DOCS[(provider, dimension)][0]
            text = f"For this test fixture, {provider} improves data coverage over time."
        elif (provider, dimension) in _DOCS:
            url, text = _DOCS[(provider, dimension)]
        else:
            return []
        return [{"source_url": url, "relevant_passage": text}]

    return DocumentSearchTool(search_function=search)


def test_combined_comparison_runs_through_app_and_persists_structured_results(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow, "google_driving_coverage", lambda *_: None)
    calls = []
    client = _client()
    with closing(connect(tmp_path / "cases.db")) as con:
        result = run_case(con, _QUERY, client=client, search=_search(calls))
        assert result["status"] == "final", result["critic"]
        assert not validate_outputs(result["outputs"])
        comparison = result["outputs"]["comparison"]
        assert cases.load_state(con, result["case_id"])["last_result"]["outputs"]["comparison"] == comparison
        trace_calls = [json.loads(row["output_json"]) for row in con.execute(
            "SELECT output_json FROM trace_steps WHERE trace_id=? AND component='tool_registry' ORDER BY id",
            (result["trace_id"],),
        )]
        assert trace_calls == result["tool_calls"]
        assert [call["tool_name"] for call in trace_calls] == ["document_search"] * 4 + ["compare_providers"]
        assert all(call["input_validation"] == call["output_validation"] == "passed" for call in trace_calls)

    assert comparison["dimensions"] == ["pricing", "limits", "coverage"]
    assert comparison["equivalent_requirements"] == {
        "api": "directions", "region": "India", "monthly_volume_raw": "150,000 requests per month",
        "monthly_workload": {"quantity": 150000, "unit": "requests"},
    }
    assert {(provider, facet) for provider, facet, _ in calls} == {
        (provider, facet) for provider in _PROVIDERS[:2] for facet in ("limits", "coverage")
    }
    prompts = [json.loads(call.args[0][-1]["content"]) for call in client.complete.call_args_list
               if call.kwargs.get("response_format")]
    document_prompts = [prompt["enquiry"] for prompt in prompts if "passages" in prompt]
    assert len(document_prompts) == 4
    assert all("Directions in India, 150,000 requests per month" in question for question in document_prompts)
    assert all("150,000" not in query for _, _, query in calls)
    results = {row["provider"]: row for row in comparison["provider_results"]}
    assert results["Google Maps Platform"]["pricing"]["estimates"][0]["monthly_cost"] == "120.00"
    assert results["Mapbox"]["pricing"]["estimates"][0]["monthly_cost"] == "100.00"
    assert comparison["assumptions"] and any("eligibility" in note for note in comparison["assumptions"])
    assert comparison["notes"] is None
    draft = result["response_draft"]
    assert "Limits:" in draft["draft_text"] and "Coverage:" in draft["draft_text"]
    assert set(comparison["source_urls"]) == {citation["url"] for citation in draft["citations"]}
    for provider, row in results.items():
        assert all(row[facet]["status"] == "verified" for facet in comparison["dimensions"])
        for estimate in row["pricing"]["estimates"]:
            assert estimate["source_references"] and estimate["components"][0]["quantity"] == 150000
        for facet in ("limits", "coverage"):
            url, text = _DOCS[(provider, facet)]
            assert row[facet]["findings"] == [{"url": url, "span": text}]


def test_combined_comparison_flags_missing_results_per_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow, "google_driving_coverage", lambda *_: None)
    calls = []
    query = _QUERY.replace("Google Maps and Mapbox Directions", "Google Maps, Mapbox, and Mappls Directions")
    with closing(connect(tmp_path / "cases.db")) as con:
        result = run_case(
            con, query, client=_client(),
            search=_search(calls, missing={("Mapbox", "coverage")}, generic={("Google Maps Platform", "coverage")}),
        )
    assert result["status"] == "final", result["critic"]
    assert len(result["tool_calls"]) == 7
    assert result["step_count"] <= 10
    assert not validate_outputs(result["outputs"])
    comparison = result["outputs"]["comparison"]
    rows = {row["provider"]: row for row in comparison["provider_results"]}
    assert rows["Mapbox"]["coverage"]["status"] == "missing_evidence"
    assert rows["Mapbox"]["coverage"]["findings"] == []
    assert rows["Mapbox"]["coverage"]["reason"]
    assert rows["Mappls (MapmyIndia)"]["pricing"]["status"] == "missing_evidence"
    assert rows["Mappls (MapmyIndia)"]["limits"]["status"] == "verified"
    assert rows["Google Maps Platform"]["coverage"]["status"] == "missing_evidence"
    assert rows["Google Maps Platform"]["limits"]["status"] == "verified"
    assert comparison["notes"]


def test_combined_comparison_clarifies_missing_region_before_search(tmp_path):
    calls = []
    with closing(connect(tmp_path / "cases.db")) as con:
        result = run_case(con, _QUERY.replace(" in India", ""), client=_client(), search=_search(calls))
    assert result["status"] == "clarification_needed"
    assert result["clarifying_questions"]["questions"][0]["field"] == "region"
    assert not calls


def test_combined_matrix_pricing_compares_the_same_elements():
    question = "Compare Mapbox and Ola Distance Matrix for a 4×5 grid, 6,000 calls per month, without traffic."
    workload = monthly_workload("distance_matrix", question, None)
    assert workload == {"quantity": 6000, "unit": "matrix_requests", "origins": 4, "destinations": 5}
    assert monthly_workload("distance_matrix", "Compare 6,000 matrix requests per month", None) is None

    prices = compare_prices(["Mapbox", "Ola Maps"], {
        "api": "distance_matrix", "region": "India", "monthly_workload": workload,
    }, question)
    for price in prices.values():
        assert price["status"] == "verified"
        component, = price["estimates"][0]["components"]
        assert component["quantity"] == 120000
        assert component["billing_unit"] in {"pair", "element"}


def test_comparison_does_not_treat_autocomplete_requests_as_sessions():
    question = "Compare Mapbox and Google Autocomplete for 150,000 requests per month in India."
    workload = monthly_workload("autocomplete", question, None)
    prices = compare_prices(["Mapbox", "Google Maps Platform"], {
        "api": "autocomplete", "region": "India", "monthly_workload": workload,
    }, question)
    assert prices["Mapbox"]["status"] == "missing_evidence"
    assert "sessions" in prices["Mapbox"]["reason"]
    assert prices["Google Maps Platform"]["status"] == "verified"


def test_combined_coverage_pairs_the_split_table_and_preserves_mapbox_gap(tmp_path, monkeypatch):
    from copilot.rag.document_indexing import bm25

    table_url = "https://developers.google.com/maps/coverage"
    header = "| Region code | Country/Region | Driving Directions / Snap to Roads |"
    legend = "| ⬤ | The feature is available in the area, with good data quality and availability. |"
    india = "| IN | India | ⬤ |"
    # The heading and country row occur in different indexed chunks.
    monkeypatch.setattr(bm25, "load_chunks", lambda: [
        {"doc_url": table_url, "text": header + "\n" + legend},
        {"doc_url": table_url, "text": india},
    ])
    _google_table.cache_clear()
    calls = []
    try:
        with closing(connect(tmp_path / "cases.db")) as con:
            result = run_case(con, _QUERY, client=_client(), search=_search(calls, missing={("Mapbox", "coverage")}))
    finally:
        _google_table.cache_clear()

    assert result["status"] == "final", result["critic"]
    assert not validate_outputs(result["outputs"])
    comparison = result["outputs"]["comparison"]
    rows = {row["provider"]: row for row in comparison["provider_results"]}
    google = rows["Google Maps Platform"]["coverage"]
    assert google["status"] == "verified"
    assert "standard driving coverage in India" in google["summary"]
    assert [item["span"] for item in google["findings"] if item["url"] == table_url] == [header, india, legend]
    assert any(item["url"].endswith("/routes/quick-reference") for item in google["findings"])
    assert ("Google Maps Platform", "coverage") not in {(provider, facet) for provider, facet, _ in calls}
    mapbox = rows["Mapbox"]["coverage"]
    assert mapbox["status"] == "missing_evidence" and mapbox["findings"] == []
    assert "standard driving profile" in mapbox["reason"]
