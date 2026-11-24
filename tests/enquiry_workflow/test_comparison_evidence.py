import pytest
from pydantic import ValidationError

from copilot.enquiry_workflow.comparison_evidence import matrix_comparison, matrix_shape, pricing_scope
from copilot.enquiry_workflow.retrieval import rag_document_search
from copilot.enquiry_workflow.routing import asks_for_estimate, pricing_context
from copilot.registered_tools.tool_contracts import AppComparisonInput


def test_capitalized_requests_in_price_followup_keep_workload_and_scope():
    prior = "What is the estimated charge for 41,000 Google Places Autocomplete Requests per month on the global price card?"
    latest = "New Places API SKU, please. Show USD."
    query = pricing_context(latest, prior, pricing_intent=False)

    assert asks_for_estimate(latest, query, pricing_intent=False) == (True, True)
    assert pricing_scope("autocomplete", query, latest, []) == "autocomplete_global_price"


def test_scoped_search_returns_the_documented_many_to_many_matrix_limits(monkeypatch):
    from copilot.rag.document_indexing import bm25

    google = "https://developers.google.com/maps/documentation/routes/compute_route_matrix"
    mappls = "https://developer.mappls.com/documentation/sdk/rest-apis/mappls-distance-matrix-api/readme"
    references = [
        (google, "The number of elements cannot exceed 625 for routes that are not TRANSIT routes. "
                 "If you specify origins or destinations using address or place ID , you specify up to 50 total this way."),
        (mappls, "Please note that maximum number of points are limited to 100 only including source and secondary positions."),
        (mappls, "To specify which of the coordinates supplied in the URL are to be treated as source position for many to many "
                 "distance matrix calculation, indicate that coordinate pair's index."),
    ]
    chunks = [
        {"chunk_id": str(index), "text": text, "doc_url": url, "fetched_at": "2026-11-01"}
        for index, (url, text) in enumerate(references)
    ]
    monkeypatch.setattr(bm25, "load_chunks", lambda: chunks)
    query = "Which providers can accept a 29×31 distance matrix in one request?"
    assert matrix_shape(query) == (29, 31)
    passages = rag_document_search().search(query, max_results=7, scope="matrix_limits")
    draft = matrix_comparison(29, 31, passages)["draft"]

    assert "899 elements" in draft["draft_text"]
    assert "60 input points" in draft["draft_text"]
    assert "Mappls (MapmyIndia) Distance Matrix: fits" in draft["draft_text"]
    assert "Google Maps Platform Compute Route Matrix: exceeds" in draft["draft_text"]
    assert any("many to many" in citation["span"] for citation in draft["citations"])


def test_matrix_calculator_requires_positive_dimensions():
    query = "Which providers can accept this in one call?"
    with pytest.raises(ValidationError):
        AppComparisonInput(operation="matrix_limits", query=query, origins=0, destinations=31)


def test_pure_quote_does_not_repeat_sku_evidence_search():
    quote = "Quote legacy Google Distance Matrix for 300,000 elements per month."
    assert pricing_scope("distance_matrix", quote, quote, []) is None
