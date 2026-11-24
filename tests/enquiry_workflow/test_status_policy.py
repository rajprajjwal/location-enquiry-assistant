"""Billing guidance and customer-status assertions have different evidence needs."""
import pytest
from copilot.enquiry_workflow.billing_policy import billing_policy_continuation


def history(message):
    return [{'role': 'user', 'text': message}, {'role': 'assistant', 'text': 'Are you on a contract?'}]


def test_billing_policy_continuation_does_not_assume_service_has_stopped():
    earlier = "We're on Ola Maps self-service. Our credit balance went negative. Will routing calls stop?"
    assert billing_policy_continuation("I don't know yet. Please proceed on what I already said.", history(earlier))


@pytest.mark.parametrize('latest', [
    'Please escalate this to a human.',
    'Our routing calls have now stopped.',
    'We cannot route. Please proceed.',
    'I need a refund. Please go ahead.',
    'Please contact our account manager and investigate.',
])
def test_new_intervention_evidence_is_not_suppressed(latest):
    assert not billing_policy_continuation(latest, history('Our credit balance is negative. Will routing calls stop?'))


def test_confirmed_prior_interruption_does_not_become_a_policy_question():
    assert not billing_policy_continuation('Please proceed.', history(
        'Our credit balance is negative. Calls have stopped. Will routing service fail again?'))


def test_unrelated_history_is_not_a_billing_policy_question():
    assert not billing_policy_continuation('Please proceed.', history('How much does a Directions request cost?'))


@pytest.mark.parametrize(('message', 'expected'), [
    ('Existing Google project: estimate our matrix bill.', 'existing'),
    ('Existing Google Cloud project: estimate our matrix bill.', 'existing'),
    ('A new SKU is available for an existing Google project.', 'existing'),
    ("We're on Ola Maps self-service.", 'existing'),
    ("We're on a call with Ola Maps.", 'unknown'),
    ('If we had an existing Google project, what would change?', 'unknown'),
    ('Can I use an existing Google project?', 'unknown'),
    ("Suppose we're on Mapbox. What then?", 'unknown'),
])
def test_provider_modifiers_do_not_hide_or_invent_status(message, expected):
    from copilot.safety.customer_evidence import customer_status
    from copilot.safety.escalation_policy import policy
    assert customer_status(message, policy()['customer_status']) == expected


def test_policy_continuation_uses_sales_without_a_model_handoff():
    from unittest.mock import patch
    from copilot.enquiry_workflow.escalation import route_enquiry, handoff_proposal
    from tests.enquiry_workflow.test_escalation import parsed_for
    query = "I don't know yet. Please proceed on what I already said."
    earlier = "We're on Ola Maps self-service. Our credit balance went negative. Will routing calls stop?"
    with patch('copilot.enquiry_workflow.escalation._model_category') as model:
        route = route_enquiry(query, parsed_for(query), history=history(earlier))
    model.assert_not_called()
    assert route['owner'] == 'Account team (Sales)'
    assert route['should_escalate'] is False
    assert route['ownership_review']['customer_status'] == 'existing'
    assert handoff_proposal(route) is None


def test_actual_interruption_keeps_model_assessment():
    from types import SimpleNamespace
    from unittest.mock import patch
    from copilot.enquiry_workflow.escalation import route_enquiry, handoff_proposal
    from tests.enquiry_workflow.test_escalation import parsed_for
    query = 'Our routing calls have now stopped. Please proceed.'
    with patch('copilot.enquiry_workflow.escalation._model_category', return_value=SimpleNamespace(
        category='advanced_support', reason='The customer reports stopped routing calls.')) as model:
        route = route_enquiry(query, parsed_for(query), history=history(
            'Our credit balance is negative. Will routing calls stop?'))
    model.assert_called_once()
    assert route['should_escalate']
    assert handoff_proposal(route)['approval_status'] == 'pending'
