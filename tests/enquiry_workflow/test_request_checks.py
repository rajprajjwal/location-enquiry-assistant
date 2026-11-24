"""Technical request checks must not suppress incidents or invent customer facts."""
import pytest

from copilot.enquiry_workflow.routine_triage import routine_support_assessment
from copilot.safety.customer_evidence import customer_status
from copilot.safety.escalation_policy import policy


def wrapped(message):
    return f'Customer message: "{message}" Who should own this, does it need escalating?'


@pytest.mark.parametrize('message', [
    'Our matrix endpoint returns REQUEST_DENIED from the backend.',
    'Our Directions URL with many waypoints is rejected as too long.',
])
def test_standard_configuration_and_url_checks_start_in_first_line(message):
    assert routine_support_assessment(wrapped(message))


@pytest.mark.parametrize('message', [
    'Please transfer REQUEST_DENIED to a human engineer.',
    'REQUEST_DENIED blocks all our production users.',
    'We leaked a key and now see REQUEST_DENIED.',
    'A persistent REQUEST_DENIED incident has resisted investigation.',
])
def test_intervention_evidence_remains_outside_the_guard(message):
    assert not routine_support_assessment(wrapped(message))


@pytest.mark.parametrize(('message', 'expected'), [
    ('Mapbox reverse geocoding returns locations overseas for our Indian points.', 'existing'),
    ('If Mapbox reverse returns locations for our points, what do we do?', 'unknown'),
    ('Mapbox reverse may return locations for our points.', 'unknown'),
    ('Mapbox reverse returns locations for our points if we subscribe.', 'unknown'),
    ('Our returns operator requires reverse geocoding for our stores.', 'unknown'),
])
def test_personal_result_evidence_requires_actual_use(message, expected):
    assert customer_status(message, policy()['customer_status']) == expected


@pytest.mark.parametrize(('api', 'status', 'owner'), [
    ('autocomplete', 'unknown', 'Support L1'),
    ('directions', 'unknown', 'Account team (Sales)'),
    ('autocomplete', 'new', 'Account team (Sales)'),
    ('autocomplete', 'existing', 'Support L1'),
])
def test_country_configuration_rule_is_api_scoped(api, status, owner):
    from types import SimpleNamespace
    from copilot.safety.escalation_policy import routine_owner
    parsed = SimpleNamespace(intent='coverage_limits', sub_intent='coverage_question', api=api, team='Sales')
    actual = routine_owner('Are only one country or multiple countries allowed?', parsed,
                           customer_status_override=status)
    assert actual['owner'] == owner


def test_free_allowance_guidance_does_not_capture_custom_pricing():
    from types import SimpleNamespace
    from copilot.safety.escalation_policy import routine_owner
    parsed = SimpleNamespace(intent='pricing_quote', sub_intent='pricing_estimate', api='directions', team='Sales')
    actual = routine_owner('Can our enterprise plan include free requests, and do we need to buy credits?',
                           parsed, customer_status_override='unknown')
    assert actual['owner'] == 'Account team (Sales)'
