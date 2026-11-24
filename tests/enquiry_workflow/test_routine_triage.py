"""Routine triage must preserve explicit requests and incident evidence."""
import pytest

from copilot.enquiry_workflow.routine_triage import routine_support_assessment


def enquiry(text):
    return f'Customer message: "{text}" Who should own this, and does it need escalating?'


@pytest.mark.parametrize('text', [
    'The API returns INVALID_REQUEST for our origin parameter.',
    "The request reports Invalid/missing origin.",
    'The matrix request returns MAX_ROUTE_LENGTH_EXCEEDED.',
    'Some points return ZERO_RESULTS after filtering result types.',
    'Our matrix call does not return duration_in_traffic.',
    'The provider rejects our matrix request.',
])
def test_ordinary_assessment_can_start_in_first_line(text):
    assert routine_support_assessment(enquiry(text))


@pytest.mark.parametrize('text', [
    'Please escalate INVALID_REQUEST to a human.',
    'Persistent INVALID_REQUEST continues after investigation.',
    'ZERO_RESULTS is a sustained production regression.',
    'Production is down and all requests return INVALID_REQUEST.',
    'We exposed our key and now receive INVALID_REQUEST.',
    'Our security team needs a human handoff for INVALID_REQUEST.',
    'Please hand off our ZERO_RESULTS case.',
    'Please transfer our INVALID_REQUEST case to the support team.',
])
def test_intervention_evidence_is_not_suppressed(text):
    assert not routine_support_assessment(enquiry(text))


def test_new_customer_policy_and_direct_customer_requests_are_preserved():
    assert not routine_support_assessment(enquiry('The API returns INVALID_REQUEST.'), customer_status='new')
    assert not routine_support_assessment('Please investigate INVALID_REQUEST with Support L2.')


def test_route_checks_the_request_before_consulting_the_handoff_model():
    from unittest.mock import create_autospec
    from copilot.enquiry_workflow.escalation import route_enquiry, handoff_proposal
    from copilot.model_gateway.client import LLMClient
    from tests.enquiry_workflow.test_escalation import parsed_for
    query = enquiry('The matrix call does not return duration_in_traffic.')
    client = create_autospec(LLMClient, instance=True)
    result = route_enquiry(query, parsed_for(query), client=client)
    assert result['owner'] == 'Support L1'
    assert not result['should_escalate']
    assert result['source'] == 'rule'
    assert handoff_proposal(result) is None
    client.complete.assert_not_called()
