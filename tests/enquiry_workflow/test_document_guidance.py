"""Regression checks for direct, citation-grounded guidance."""

import pytest

from copilot.enquiry_interpretation import interpret
from copilot.enquiry_workflow import run_enquiry
from copilot.enquiry_workflow.document_guidance import guidance_draft
from copilot.enquiry_workflow.retrieval import rag_document_search
from tests.support.helpers import ScriptedClient, completion, model_json


@pytest.mark.parametrize(("query", "api", "answer", "source_count"), [
    ("Mapbox reverse geocoding makes 25 requests per second. Will we hit the rate limit?",
     "reverse_geocode", ("expect throttling", "1,500 requests per minute", "HTTP 429"), 2),
    ("Does 12 calls per second exceed the rate limit on Mapbox reverse geocoding?",
     "reverse_geocode", ("720 requests per minute", "within the default 1,000"), 2),
    ("Will 12 calls per second be throttled on Mapbox reverse geocoding v5?",
     "reverse_geocode", ("expect throttling", "default limit", "600 requests per minute"), 2),
    ("What are the capability differences between Ola Distance Matrix and Distance Matrix Basic?",
     "distance_matrix", ("traffic-aware ETAs", "without live traffic"), 2),
    ("Could we replace Nominatim reverse geocoding with OSRM?",
     "reverse_geocode", ("OSRM Nearest", "road network", "human-readable address"), 2),
    ("What should we confirm about volume and matrix size for Google or Mapbox Matrix with traffic?",
     "distance_matrix", ("monthly origin", "peak request rate", "predicted traffic"), 2),
    ("Which providers document coverage for address autocomplete in Nepal? We use Nominatim.",
     "autocomplete", ("Mappls lists map coverage for Nepal", "candidate", "prohibits client-side autocomplete"), 3),
])
def test_guidance_uses_official_retrieval_and_answers_directly(query, api, answer, source_count):
    enquiry = {"query": query, "history": []}
    intent = "sales_qualification" if "should we confirm" in query else "coverage_limits"
    interpretation = interpret(enquiry, client=ScriptedClient([completion(model_json(
        intent=intent, api=api, team="Support",
    ))]))
    result = run_enquiry(enquiry, interpretation, search=rag_document_search(mode="bm25", rerank=False),
                         client=ScriptedClient([]))

    assert result["status"] == "final", result["critic"]
    draft = result["response_draft"]
    assert all(fragment in draft["draft_text"] for fragment in answer)
    assert len(draft["citations"]) == source_count
    assert all(citation["span"] and citation["supports_claim"] in draft["draft_text"]
               for citation in draft["citations"])


def test_quota_guidance_requires_documented_product_limit():
    query = "Is 5 requests per second too many for reverse geocoding with Mapbox?"
    assert guidance_draft(query, [{
        "source_url": "https://example.com/geocoding/",
        "relevant_passage": "Mapbox allows 500 requests per minute.",
    }]) is None
