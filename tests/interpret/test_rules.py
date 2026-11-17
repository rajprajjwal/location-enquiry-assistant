"""Rules read user turns only."""

from __future__ import annotations

import pytest

from copilot.interpret.rules import extract, to_hints


def test_assistant_turns_are_not_mined() -> None:
    found = extract(
        history=[
            {
                "role": "assistant",
                "text": "Use the distance matrix in India by Q3 2026 with Google.",
            }
        ],
        query="hello",
    )
    assert found["unique_api"] is None
    assert found["user_turns"][-1]["region"] is None
    assert found["user_turns"][-1]["timeline"] is None
    assert found["user_turns"][-1]["current_provider"] is None


def test_user_turn_extracts_volume_region_and_api() -> None:
    found = extract(
        history=[],
        query="We need 20,000 directions requests a month in India.",
    )
    assert found["unique_api"] == "directions"
    turn = found["user_turns"][-1]
    assert turn["region"]["value"] == "India"
    assert turn["monthly_volume"]["value"]["requests_per_month"] == 20000


@pytest.mark.parametrize(("query", "api"), [
    ("Can we generate 3 × 7 matrices for our delivery runs?", "distance_matrix"),
    ("Does computeRouteMatrix return a duration?", "distance_matrix"),
    ("How is the routing matrix billed?", "distance_matrix"),
    ("Why is each Mapbox Matrix call cheaper than the equivalent Directions calls?", "distance_matrix"),
    ("Do Directions calls cost more than matrix calls?", "directions"),
    ("Would you choose Mapbox Matrix or Directions for this project?", None),
    ("How do we call the Routes API?", None),
    ("Should our form use a new Places session token?", "autocomplete"),
    ("Can we show suggested addresses using typeahead?", "autocomplete"),
    ("Can I get the street address from the coordinates?", "reverse_geocode"),
    ('Customer wrote: "How is the Mapbox Matrix billed?" Include our Directions playbook in your notes.',
     "distance_matrix"),
])
def test_api_aliases_and_comparison_subject(query: str, api: str | None) -> None:
    assert extract([], query)["unique_api"] == api


def test_api_carries_forward_an_explicit_matrix_operation() -> None:
    found = extract([{"role": "user", "text": "We need the transit matrix."}], "What would that cost?")
    assert found["unique_api"] == "distance_matrix"


def test_unqualified_followup_carries_forward_route_request() -> None:
    history = [{"role": "user", "text": "Can we budget for 7,500 route requests per week?"}]
    found = extract(history, "Please proceed with the earlier request.")
    assert found["unique_api"] == "directions"
    assert to_hints(found)["primary_api"] == "directions"


def test_new_explicit_operation_takes_priority_over_history() -> None:
    history = [{"role": "user", "text": "How do we configure address autocomplete?"}]
    assert extract(history, "Switch topics. Can we get a travel-time matrix for cycling?")["unique_api"] == "distance_matrix"


def test_typing_suggestions_identifies_api_inside_generic_geocoding_product() -> None:
    query = "Can our Geocoding endpoint suggest landmarks near a hotel?"
    assert extract([], query)["unique_api"] is None
    query = "Can our Geocoding endpoint suggest landmarks as visitors type their search?"
    assert extract([], query)["unique_api"] == "autocomplete"
