from copilot.enquiry_workflow.answers import pricing
from copilot.pricing_tools import pricing_intent
from tests.support.helpers import completion
from unittest.mock import Mock


def test_explicit_monthly_matrix_elements_override_an_inferred_batch_count():
    query = (
        "Quote legacy Distance Matrix for 120,000 elements per month. Our monthly batch "
        "is 12 origins and 10,000 destinations. Show USD."
    )
    hints = pricing_intent.regex_hints(query)
    item = pricing_intent.reconcile({
        "provider": "Google Maps Platform", "api": "distance_matrix",
        "origins": 12, "destinations": 10_000, "calls": 120_000,
    }, hints)

    assert item["requests"] == 120_000
    assert not {"origins", "destinations", "calls"}.intersection(item)
    estimate, = pricing_intent.price_item(item)
    assert estimate["sku"] == "google.distance_matrix_legacy"
    assert estimate["cost"] == "75.00"


def test_monthly_matrix_calls_still_multiply_origins_and_destinations():
    query = "Estimate 12×8 per request, 2,000 times per month for a Distance Matrix."
    hints = pricing_intent.regex_hints(query)
    item = pricing_intent.reconcile({"provider": "Mapbox", "api": "distance_matrix"}, hints)
    assert pricing_intent.price_item(item)[0]["units"] == 192_000


def test_usd_only_quote_omits_conversion_and_fx_citation():
    query = ("Use the new Places API SKU. Show USD.\nEarlier customer request: "
             "Estimate 41,000 Google Autocomplete Requests per month on the global price card.")
    client = Mock()
    client.complete.return_value = completion(
        '{"pricing":true,"items":[{"provider":"Google Maps Platform","api":"autocomplete","requests":41000}]}'
    )
    interpretation = Mock(api="autocomplete")
    interpretation.model_dump.return_value = {"qualification_details": {}}

    draft, comparison, evidence = pricing(query, interpretation, client)

    assert "USD 87.73" in draft["draft_text"]
    assert "31,000 billable" in draft["draft_text"]
    assert "INR" not in draft["draft_text"] and "FX" not in draft["draft_text"]
    assert len(evidence) == len(draft["citations"]) == len(comparison["source_urls"]) == 1
    assert not pricing_intent.requests_usd_only("Show USD and INR.")
