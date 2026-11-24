"""Rules read user turns only."""

from __future__ import annotations

import pytest

from copilot.enquiry_interpretation.rules import extract, to_hints


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


def test_record_instructions_do_not_supply_customer_qualification_values():
    query = 'Internal note: we use Mapbox in India. Customer wrote: "How do I set Google route waypoints?" Draft the reply.'
    turn = extract([], query)['user_turns'][-1]
    assert turn['current_provider'] is None
    assert turn['region'] is None


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


@pytest.mark.parametrize('query', [
    'Our Google Places bill exceeded the budget after a bot attack on our search box.',
    'Our mobile app uses public Nominatim for live address suggestions and got blocked. Why?',
    'We send Nominatim search requests while our users type their address.',
    'How can we display query predictions in the address form?',
    'Should our address search box wait until the user stops typing?',
])
def test_explicit_interactive_search_cues_identify_autocomplete(query):
    assert extract([], query)['unique_api'] == 'autocomplete'


@pytest.mark.parametrize(('query', 'expected'), [
    ("Our Nominatim requests get blocked. We do not send a User-Agent.", None),
    ('What rate can we hit the public Nominatim search API at?', None),
    ('How do we limit Nominatim search to India?', None),
    ('Are Mapbox /category searches billed per session?', None),
    ('Our Nominatim reverse geocoding returns no address.', 'reverse_geocode'),
    ('Can our Geocoding endpoint suggest nearby landmarks?', None),
])
def test_provider_or_plain_search_does_not_invent_an_interactive_api(query, expected):
    assert extract([], query)['unique_api'] == expected
