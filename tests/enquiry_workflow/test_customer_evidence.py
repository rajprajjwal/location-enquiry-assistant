"""Customer facts must distinguish actual use from possible API behaviour."""
import pytest

from copilot.safety.customer_evidence import customer_status
from copilot.safety.escalation_policy import policy


@pytest.mark.parametrize(("query", "expected"), [
    ("Google Directions: we always send intermediate stops. Which rate applies?", "existing"),
    ("Our app calls Nominatim reverse every minute. What should we change?", "existing"),
    ("We receive Google Directions responses in our integration.", "existing"),
    ("Google reverse geocoding gives ZERO_RESULTS for some coordinates.", "existing"),
    ("Our Mapbox request returns an HTTP 403 error.", "existing"),
    ("Google Distance Matrix does not return duration_in_traffic.", "existing"),
    ("Can we get traffic-aware Google Directions routes?", "unknown"),
    ("Should we send intermediate stops to Google Directions?", "unknown"),
    ("Our app will call Nominatim reverse.", "unknown"),
    ("If our app calls Nominatim reverse, what happens?", "unknown"),
    ("Our app does not call Nominatim reverse.", "unknown"),
    ("Our app used to call Nominatim reverse.", "unknown"),
    ("Can Google reverse geocoding return ZERO_RESULTS?", "unknown"),
    ("Does Google Distance Matrix return 429 when busy?", "unknown"),
    ("Our returns operator needs 4,500,000 reverse-geocoding lookups per month.", "unknown"),
    ("We are not an existing customer of Google Maps.", "unknown"),
    ("If we use Google Directions, what would it cost?", "unknown"),
    ("We are a new customer. Google Directions returns REQUEST_DENIED.", "new"),
    ("We are an existing customer. We need a price estimate.", "existing"),
])
def test_customer_evidence_requires_an_asserted_fact(query, expected):
    assert customer_status(query, policy()["customer_status"]) == expected


def test_reported_behaviour_is_optional_when_actual_use_detection_is_disabled():
    assert customer_status("Google reverse geocoding gives ZERO_RESULTS.",
                           policy()["customer_status"], actual_use=False) == "unknown"
