"""Separate asserted workloads, documented allowances and estimate assumptions."""
import pytest

from copilot.qualification.workload import (
    from_text, monthly_volume_from_enquiry, monthly_volume_proposal,
    normalize_monthly_volume, scenario_volume_from_enquiry, scenario_volume_from_text,
)


@pytest.mark.parametrize('text', [
    'The documentation allows 50,000 requests per month.',
    'Google includes 50,000 requests per month in the free tier.',
    'Our subscription includes 50,000 calls per month.',
    'The API supports 50,000 requests per month.',
    'The provider limit is 50,000 requests per month.',
    'Do we send 50,000 requests per month?',
    'We might send 50,000 requests per month.',
    'If we send 50,000 requests per month, this will be sufficient.',
    'We do not send 50,000 requests per month.',
])
def test_allowances_questions_and_uncertainty_do_not_confirm_usage(text):
    assert from_text(text) is None
    assert monthly_volume_from_enquiry({'query': text}) == (None, None)
    assert monthly_volume_proposal(50000, text) is None


@pytest.mark.parametrize('text', [
    'Assume 50,000 requests per month for an estimate.',
    'How much would 50,000 requests per month cost?',
    'Please estimate the cost for 50,000 requests per month.',
    'We might send 50,000 requests per month. What would it cost?',
    'If we send 50,000 requests per month, what would we pay?',
])
def test_explicit_estimate_amounts_remain_separate_scenario_inputs(text):
    assert from_text(text) is None
    assumption = scenario_volume_from_text(text)
    assert assumption['requests_per_month'] == 50000
    assert assumption['unit'] == 'requests_per_month'
    assert assumption['basis'] == 'scenario_assumption'
    assert assumption['evidence'] in text
    assert normalize_monthly_volume(assumption) is None


@pytest.mark.parametrize('text', [
    'The free tier includes 50,000 requests per month. How much is the next tier?',
    'Do we send 50,000 requests per month?',
    'We might send 50,000 requests per month.',
])
def test_no_scenario_is_invented_without_an_estimate_input(text):
    assert scenario_volume_from_text(text) is None


@pytest.mark.parametrize('text', [
    'We send 20,000 requests per month.',
    '20,000 requests per month',
    'Our workload includes 20,000 requests per month.',
    'The documentation allows 50,000 requests per month; we send 20,000 requests per month.',
    'We send 20,000 requests per month. Which provider is cheaper?',
])
def test_customer_assertions_survive_other_documentation_and_questions(text):
    parsed = from_text(text)
    assert parsed['requests_per_month'] == 20000
    assert parsed['unit'] == 'requests_per_month'


def test_current_scenario_does_not_replace_known_usage_or_use_assistant_claims():
    enquiry = {
        'query': 'Assume 50,000 requests per month for an estimate.',
        'history': [
            {'role': 'user', 'text': 'We send 20,000 requests per month.'},
            {'role': 'assistant', 'text': 'Assume 900,000 requests per month.'},
        ],
    }
    actual, actual_source = monthly_volume_from_enquiry(enquiry)
    scenario, scenario_source = scenario_volume_from_enquiry(enquiry)
    assert actual['requests_per_month'] == 20000
    assert actual_source == 'history[0]'
    assert scenario['requests_per_month'] == 50000
    assert scenario_source == 'query'


def test_latest_actual_value_overrides_earlier_actual_usage():
    parsed, source = monthly_volume_from_enquiry({
        'query': 'Actually, we send 60,000 requests per month.',
        'history': [{'role': 'user', 'text': 'We send 20,000 requests per month.'}],
    })
    assert parsed['requests_per_month'] == 60000
    assert source == 'query'


def test_latest_asserted_clause_replaces_a_prior_value_in_the_same_message():
    parsed = from_text('We send 20,000 requests per month, but now we send 60,000 requests per month.')
    assert parsed['requests_per_month'] == 60000


def test_monthly_assertions_and_scenarios_exclude_assistant_only_history():
    enquiry = {'query': 'Please proceed.', 'history': [
        {'role': 'assistant', 'text': 'We send 20,000 requests per month.'},
        {'role': 'assistant', 'text': 'Assume 50,000 requests per month.'},
    ]}
    assert monthly_volume_from_enquiry(enquiry) == (None, None)
    assert scenario_volume_from_enquiry(enquiry) == (None, None)
