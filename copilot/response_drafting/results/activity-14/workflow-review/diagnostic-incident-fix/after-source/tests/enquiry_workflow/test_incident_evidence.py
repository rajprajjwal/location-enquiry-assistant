"""Diagnostic collection must reuse validated incident categories without rerouting."""
from copy import deepcopy

import pytest

from copilot.diagnostics.facts import build_diagnostic_state
from copilot.diagnostics.planning import plan_staff_follow_up
from copilot.diagnostics.policy import allowed_decisions
from copilot.safety.escalation import check
from copilot.safety.incident_evidence import observed_incidents
from tests.enquiry_workflow.test_additional_diagnostic_evidence import result_for, client_for

CREDIT = 'Our prepaid Ola credits ran out and autocomplete stopped for paying users. Can you restore it now?'
QUALITY = 'A customer reports Ola Autocomplete suggests a misspelt locality name that offends residents. What do we do?'
EXPOSURE = 'A developer accidentally pushed our Ola Maps API key to a public GitHub repo. What should we do right now?'


@pytest.mark.parametrize('query,category,decision,fields', [
    (CREDIT, 'billing_incident', 'credit_restoration', ['account_reference']),
    (QUALITY, 'data_quality', 'prediction_quality', ['prediction_query', 'returned_prediction']),
])
def test_shared_incident_categories_admit_the_required_collection(query, category, decision, fields):
    assert check(query)['category'] == category
    evidence = observed_incidents(query)
    assert category in evidence['categories']
    for signal in evidence['categories'][category]:
        assert query[signal['start']:signal['end']] == signal['text']
    enquiry = {'query': query}
    assert allowed_decisions(build_diagnostic_state(enquiry), query, 'autocomplete', enquiry=enquiry) == [decision]
    original = result_for(query)
    before = deepcopy(original)
    updated = plan_staff_follow_up(original, enquiry, client=client_for())
    assert updated['follow_up_selection']['facts'] == fields
    assert len(updated['outputs']['clarifying_questions']['questions']) == 1
    for field in ('status', 'pending_reply', 'clarifying_questions', 'proposed_actions'):
        assert updated[field] == before[field]
    for field in ('responsible_role', 'next_action', 'proposed_record_update'):
        assert updated['outputs'][field] == before['outputs'][field]


@pytest.mark.parametrize('query', [
    'If our credits ran out and autocomplete stopped, could you restore it?',
    'The docs describe credits ran out and autocomplete stopped. How would we restore it?',
    'Our credits have not run out and autocomplete stopped. Can you restore it?',
    'Our credits ran out but autocomplete has not stopped. Can you restore it?',
    'Our credits ran out and autocomplete stopped. Please do not restore it.',
    'Our credits ran out. Please restore the service.',
    'Our credits ran out. We want the service restored.',
    'Our credits ran out and autocomplete stopped, but we restored the service.',
    'Can autocomplete suggest a misspelt locality that offends residents?',
    'The documentation describes a misspelt locality that offends residents.',
    'Our autocomplete locality is not misspelt and no result offends residents.',
    'Our autocomplete locality was misspelt but we corrected the data.',
])
def test_negated_hypothetical_documentation_or_resolved_incidents_do_not_collect(query):
    enquiry = {'query': query}
    actual = allowed_decisions(build_diagnostic_state(enquiry), query, 'autocomplete', enquiry=enquiry)
    assert not {'credit_restoration', 'prediction_quality'} & set(actual)


def test_resolution_does_not_suppress_a_later_different_incident():
    query = 'We restored the billing service. Our autocomplete now suggests a misspelt locality.'
    enquiry = {'query': query}
    assert allowed_decisions(build_diagnostic_state(enquiry), query, 'autocomplete', enquiry=enquiry) == ['prediction_quality']


def test_negated_resolution_does_not_close_an_active_billing_incident():
    query = 'Our credits ran out and autocomplete stopped. It has not been restored. Please intervene.'
    assert 'billing_incident' in observed_incidents(query)['categories']
    enquiry = {'query': query}
    assert allowed_decisions(build_diagnostic_state(enquiry), query, 'autocomplete', enquiry=enquiry) == ['credit_restoration']


def test_non_autocomplete_data_quality_does_not_select_prediction_collection():
    query = 'Our reverse geocoding returns the wrong city name.'
    enquiry = {'query': query}
    assert 'data_quality' in observed_incidents(query)['categories']
    assert 'prediction_quality' not in allowed_decisions(build_diagnostic_state(enquiry), query, 'reverse_geocode', enquiry=enquiry)


def test_actual_public_credential_commit_collects_only_incident_metadata():
    enquiry = {'query': EXPOSURE}
    evidence = observed_incidents(EXPOSURE)
    assert check(EXPOSURE)['category'] == 'security_incident'
    assert evidence['credential_exposure']
    assert allowed_decisions(build_diagnostic_state(enquiry), EXPOSURE, 'directions', enquiry=enquiry) == ['credential_exposure']
    original = result_for(EXPOSURE, api='directions')
    before = deepcopy(original)
    updated = plan_staff_follow_up(original, enquiry, client=client_for())
    assert [q['field'] for q in updated['outputs']['clarifying_questions']['questions']] == ['exposure_time', 'unusual_usage_spikes']
    for field in ('status', 'pending_reply', 'clarifying_questions', 'proposed_actions'):
        assert updated[field] == before[field]
    for field in ('responsible_role', 'next_action', 'proposed_record_update'):
        assert updated['outputs'][field] == before['outputs'][field]


@pytest.mark.parametrize('query', [
    'A developer pushed source code to a public GitHub repo, but the API key was not included.',
    'Our API key is safe, but an unrelated document leaked publicly.',
    'We are investigating a bot attack against the API key.',
    'If a developer pushed our API key to a public GitHub repo, what would we do?',
    'The API key was not pushed to a public GitHub repo.',
])
def test_security_category_or_public_repository_alone_does_not_prove_credential_exposure(query):
    enquiry = {'query': query}
    assert not observed_incidents(query)['credential_exposure']
    assert 'credential_exposure' not in allowed_decisions(build_diagnostic_state(enquiry), query, 'directions', enquiry=enquiry)
