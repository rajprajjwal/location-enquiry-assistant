"""Verify pricing evidence requirements without changing workflow decisions."""
from unittest.mock import Mock

import pytest

from copilot.diagnostics.facts import build_diagnostic_state
from copilot.diagnostics.planning import plan_staff_follow_up
from copilot.pricing_tools.qualification import comparison_qualification

PROVIDERS = ['Google Maps Platform', 'Mapbox']


@pytest.mark.parametrize('suffix,region,fields', [
    ('', None, ['billing_country', 'usage_geography']),
    (' Billing country is India.', None, ['usage_geography']),
    (' Primary usage is India.', None, ['billing_country']),
    (' Billing country is India. Primary usage is India.', None, []),
    ('', 'Germany', []),
])
def test_only_missing_price_eligibility_is_requested(suffix, region, fields):
    enquiry = {'query': 'Compare Google and Mapbox reverse geocoding costs for 4M monthly requests.' + suffix}
    requirements = comparison_qualification(enquiry['query'], PROVIDERS, region)
    result = {
        'status': 'final', 'clarifying_questions': {'needed': False, 'questions': []},
        'outputs': {'next_action': {'action_type': 'answer_directly'}},
        'diagnostic_context': {'state': build_diagnostic_state(enquiry).model_dump(mode='json'),
                               'retrieved_evidence': [], 'pricing_requirements': requirements},
    }
    client = Mock()
    updated = plan_staff_follow_up(result, enquiry, client=client)
    assert updated['follow_up_selection'].get('facts', []) == fields
    assert updated['status'] == result['status']
    assert updated['clarifying_questions'] == result['clarifying_questions']
    assert updated['outputs']['next_action'] == result['outputs']['next_action']
    client.complete.assert_not_called()


@pytest.mark.parametrize('query,providers', [
    ('Compare on the global price card.', PROVIDERS),
    ('Compare assuming India pricing eligibility.', PROVIDERS),
    ('Estimate Google requests.', ['Google Maps Platform']),
    ('Compare Mapbox and Ola.', ['Mapbox', 'Ola Maps']),
])
def test_scope_does_not_require_unneeded_geography(query, providers):
    assert not comparison_qualification(query, providers, None)['applicable']


def test_billing_country_does_not_supply_operating_region():
    query = 'Compare Google and Mapbox costs. Billing country is India.'
    requirements = comparison_qualification(query, PROVIDERS, 'India')
    assert requirements['usage_geography'] is None
    state = build_diagnostic_state({'query': query})
    assert state.facts['billing_country'].value == 'India'
    assert 'usage_geography' not in state.facts


def test_active_region_question_and_pending_reply_remain_unchanged():
    enquiry = {'query': 'Compare Google and Mapbox costs for 4M monthly requests.'}
    active = {'field': 'region', 'text': 'Which region?'}
    result = {
        'status': 'clarification_needed', 'pending_reply': {'field': 'region'},
        'clarifying_questions': {'needed': True, 'questions': [active]},
        'outputs': {}, 'diagnostic_context': {
            'state': build_diagnostic_state(enquiry).model_dump(mode='json'), 'retrieved_evidence': [],
            'pricing_requirements': comparison_qualification(enquiry['query'], PROVIDERS, None),
        },
    }
    updated = plan_staff_follow_up(result, enquiry)
    assert updated['clarifying_questions'] == result['clarifying_questions']
    assert updated['pending_reply'] == result['pending_reply']
    questions = updated['outputs']['clarifying_questions']['questions']
    assert len(questions) == 1 and questions[0]['field'] == 'region'
    assert 'billing account' in questions[0]['text']


def test_declined_pricing_follow_up_stays_empty():
    enquiry = {'query': 'Please proceed with what we know.',
               'history': [{'role': 'user', 'text': 'Compare Google and Mapbox pricing.'}]}
    result = {
        'clarifying_questions': {'needed': False, 'questions': []}, 'outputs': {},
        'diagnostic_context': {'state': build_diagnostic_state(enquiry).model_dump(mode='json'),
                               'retrieved_evidence': [],
                               'pricing_requirements': comparison_qualification('Compare costs.', PROVIDERS, None)},
    }
    updated = plan_staff_follow_up(result, enquiry)
    assert updated['outputs']['clarifying_questions']['questions'] == []
    assert updated['follow_up_selection']['status'] == 'declined'


def test_workflow_publishes_pricing_requirements_to_shared_state(tmp_path, monkeypatch):
    from contextlib import closing
    from copilot.case_storage import cases
    from copilot.case_storage.db import connect
    from copilot.enquiry_workflow import workflow
    from copilot.enquiry_workflow.cases import run_case
    from copilot.response_drafting.schemas import validate_outputs
    from tests.enquiry_workflow.test_combined_comparison import _QUERY, _client, _search

    monkeypatch.setattr(workflow, 'google_driving_coverage', lambda *_: None)
    with closing(connect(tmp_path / 'comparison.db')) as con:
        result = run_case(con, _QUERY, client=_client(), search=_search([]))
        requirements = result['diagnostic_context']['pricing_requirements']
        assert requirements['applicable'] and requirements['usage_geography'] == 'India'
        assert result['follow_up_selection']['facts'] == ['billing_country']
        assert result['status'] == 'final' and not validate_outputs(result['outputs'])
        assert cases.load_state(con, result['case_id'])['pending_clarification'] is None
        assert cases.load_state(con, result['case_id'])['last_result']['outputs'] == result['outputs']
