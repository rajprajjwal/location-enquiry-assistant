"""Verify requested checklists reuse customer facts without creating intake state."""
from copy import deepcopy

import pytest

from copilot.enquiry_interpretation import interpret
from copilot.qualification.checklist import checklist_draft
from copilot.response_drafting.schemas import validate_outputs
from copilot.response_drafting.drafter import build_support_output
from tests.support.helpers import ScriptedClient, completion, model_json


def interpretation(enquiry, api='distance_matrix', intent='sales_qualification'):
    return interpret(enquiry, client=ScriptedClient([completion(model_json(
        intent=intent, api=api, team='Sales',
    ))]))


def test_requested_matrix_checklist_does_not_invent_generic_region_or_timeline_intake():
    enquiry = {'query': 'A dispatch prospect needs ETAs between drivers and jobs. What should we ask before recommending a distance-matrix API?'}
    parsed = interpretation(enquiry)
    draft = checklist_draft(enquiry, parsed, [])
    text = draft['draft_text']
    assert 'number of origins per matrix' in text
    assert 'number of destinations per matrix' in text
    assert 'Mapbox driving-traffic' not in text
    assert 'target countries or regions' not in text and 'launch date' not in text
    assert draft['citations'] == []
    assert 'No provider-specific claims have been verified.' in text
    assert not validate_outputs(build_support_output(draft, parsed, enquiry['query']))


@pytest.mark.parametrize('storage, expected', [
    ('We must store results.', False),
    ('We do not store results.', False),
    ('We may store results.', True),
])
def test_known_language_and_storage_polarity_are_not_repeated(storage, expected):
    enquiry = {'query': 'A prospect needs reverse geocoding with addresses shown in Hindi. ' + storage +
               ' What should we ask before recommending a provider?'}
    parsed = interpretation(enquiry, api='reverse_geocode')
    draft = checklist_draft(enquiry, parsed, [])
    assert 'required output languages' not in draft['draft_text']
    assert ('whether results must be stored' in draft['draft_text']) is expected
    assert 'peak requests per second' in draft['draft_text']


def test_history_supplied_facts_are_reused_without_changing_the_inputs():
    enquiry = {'query': 'What should we ask before recommending a reverse-geocoding API?',
               'history': [{'role': 'user', 'text': 'Addresses should be shown in Hindi. We must store results.'}],
               'known_facts': [{'field': 'region', 'value': 'India', 'source': 'history'}]}
    parsed = interpretation(enquiry, api='reverse_geocode')
    passages = [{'source_url': 'https://docs.example.test/reverse',
                 'relevant_passage': 'The reverse endpoint accepts latitude and longitude.'}]
    original = deepcopy(enquiry), parsed.model_dump(mode='json'), deepcopy(passages)
    draft = checklist_draft(enquiry, parsed, passages)
    assert enquiry == original[0] and parsed.model_dump(mode='json') == original[1] and passages == original[2]
    assert 'required output languages' not in draft['draft_text']
    assert 'whether results must be stored' not in draft['draft_text']


def test_exact_references_are_separate_from_checklist_advice_and_bounded():
    enquiry = {'query': 'What should we ask before recommending a distance-matrix API?'}
    parsed = interpretation(enquiry)
    passages = [{'source_url': f'https://docs.example.test/{i}',
                 'relevant_passage': f' Exact provider reference {i}. '} for i in range(4)]
    passages.insert(1, deepcopy(passages[0]))
    draft = checklist_draft(enquiry, parsed, passages)
    assert len(draft['citations']) == 3
    assert [c['span'] for c in draft['citations']] == [f'Exact provider reference {i}.' for i in range(3)]
    assert all(c['supports_claim'] == c['span'] and c['quote_or_summary'] == 'verbatim' for c in draft['citations'])
    assert draft['draft_text'].index('Retrieved documentation excerpts (reference only):') > draft['draft_text'].index('Could you confirm')
    assert all(c['span'] in draft['draft_text'] for c in draft['citations'])


def test_bad_or_empty_references_do_not_create_citations():
    enquiry = {'query': 'What should we ask before recommending a distance-matrix API?'}
    parsed = interpretation(enquiry)
    passages = [{'source_url': 'not-a-source', 'relevant_passage': 'Unsupported claim.'},
                {'source_url': 'https://docs.example.test/', 'relevant_passage': '  '},
                {'source_url': None, 'relevant_passage': 'No source.'}]
    draft = checklist_draft(enquiry, parsed, passages)
    assert draft['citations'] == []
    assert 'Unsupported claim.' not in draft['draft_text']
    assert 'No provider-specific claims have been verified.' in draft['draft_text']


def test_definition_is_not_converted_into_a_provider_checklist():
    enquiry = {'query': 'What is the Directions API?'}
    parsed = interpretation(enquiry, api='directions', intent='docs_how_to')
    assert checklist_draft(enquiry, parsed, []) is None


def test_supplied_precision_and_components_leave_only_provider_alternatives():
    enquiry = {'query': 'They only want reverse addresses at rooftop precision, and need address components. What should we ask?'}
    parsed = interpretation(enquiry, api='reverse_geocode')
    draft = checklist_draft(enquiry, parsed, [])
    assert 'whether rooftop precision must be a hard filter' not in draft['draft_text']
    assert 'structured breakdown of address elements' not in draft['draft_text']
    assert 'other providers you want to consider' in draft['draft_text']


def test_draft_does_not_treat_documentation_as_supplied_customer_requirements():
    enquiry = {'query': 'What should we ask before recommending a reverse-geocoding API?'}
    parsed = interpretation(enquiry, api='reverse_geocode')
    draft = checklist_draft(enquiry, parsed, [{'source_url': 'https://docs.example.test/reverse',
        'relevant_passage': 'We must store results, with addresses shown in Hindi.'}])
    assert 'required output languages' in draft['draft_text']
    assert 'whether results must be stored' in draft['draft_text']


def test_repeated_calls_are_identical_and_pricing_groups_are_not_duplicated():
    enquiry = {'query': 'What should we ask before recommending a distance-matrix API?'}
    parsed = interpretation(enquiry)
    pricing = {'applicable': True, 'required_facts': ['origin_count', 'billing_country']}
    before = deepcopy(pricing)
    first = checklist_draft(enquiry, parsed, [], pricing)
    assert checklist_draft(enquiry, parsed, [], pricing) == first
    assert first['draft_text'].count('number of origins per matrix') == 1
    assert 'billing account country' in first['draft_text']
    assert pricing == before


def test_all_supplied_requirements_do_not_produce_new_checklist_questions():
    enquiry = {'query': 'What should we ask before recommending a distance-matrix API?'}
    parsed = interpretation(enquiry)
    enquiry['known_facts'] = [
        {'field': 'origin_count', 'value': 10, 'source': 'history'},
        {'field': 'destination_count', 'value': 8, 'source': 'history'},
        {'field': 'traffic_required', 'value': False, 'source': 'history'},
        {'field': 'mapbox_traffic_profile', 'value': False, 'source': 'history'},
    ]
    draft = checklist_draft(enquiry, parsed, [])
    assert 'already supplied' in draft['draft_text'] or 'has supplied' in draft['draft_text']
    assert 'Could you confirm' not in draft['draft_text']
    assert draft['citations'] == []
