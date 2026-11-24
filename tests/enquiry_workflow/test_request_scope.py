"""Answer-scope options must not be mistaken for current customer requirements."""
from copy import deepcopy

import pytest

from copilot.diagnostics.facts import build_diagnostic_state
from copilot.qualification.contract import QualificationContext
from copilot.qualification.decisions import requirement_plan
from copilot.qualification.request_scope import request_constraints


def test_a_question_about_which_questions_to_ask_does_not_supply_the_requested_options():
    assumptions = request_constraints({'query':'What should we ask about voice or text instructions and future departures before recommending a Directions API?'})
    assert 'instruction_modality' not in assumptions
    assert 'departure_time_mode' not in assumptions


@pytest.mark.parametrize('query,field,value', [
    ('Which languages are supported in Google Directions text instructions?', 'instruction_modality', 'text'),
    ('Does this API return spoken navigation instructions?', 'instruction_modality', 'voice'),
    ('Compare voice and text instructions for navigation.', 'instruction_modality', ['voice', 'text']),
    ('What is the difference between voice and text instructions?', 'instruction_modality', ['voice', 'text']),
    ('Which traffic-aware setting handles future departures in Google Directions?', 'departure_time_mode', 'future'),
    ('How do I set departure_time=now?', 'departure_time_mode', 'now'),
    ('Compare routing now and for future departures.', 'departure_time_mode', ['now', 'future']),
    ('Recommend a self-hosted Directions API for a hobby project.', 'hosting_preference', 'self-hosted'),
    ('Compare a self-hosted endpoint versus a managed API.', 'hosting_preference', ['self-hosted', 'managed']),
    ('Compare Google Maps and Mapbox Matrix.', 'alternative_providers', ['Google Maps Platform', 'Mapbox']),
])
def test_explicit_answer_scope_has_exact_evidence(query, field, value):
    constraint = request_constraints({'query': query})[field]
    assert constraint.value['value'] == value
    assert constraint.value['basis'] == 'requested_scope'
    assert query[constraint.start:constraint.end] == constraint.evidence


def test_requested_mode_prevents_a_redundant_question_without_supplying_actual_usage():
    enquiry = {'query': 'Which languages are supported in Google Directions text instructions?'}
    state = build_diagnostic_state(enquiry)
    before = state.model_dump(mode='json')
    constraints = request_constraints(enquiry)
    context = QualificationContext(api='directions', intent='docs_how_to', assumptions=constraints)
    selected = requirement_plan(context, state,
        [{'fields': ['instruction_modality'], 'decision_impact': 'Choose voice or text support.', 'required': True}],
        enquiry['query'])
    assert selected.decisions == []
    assert 'instruction_modality' not in context.facts
    assert state.model_dump(mode='json') == before


@pytest.mark.parametrize('query', [
    'Which instruction modality should we choose?',
    'The documentation lists text instructions. What else is available?',
    'Which departure time should we use?',
    'We might use voice instructions.',
    'Which provider should we choose?',
    'Does a text search API provide navigation instructions?',
])
def test_no_scope_is_invented_from_unknown_or_documentation_only_mentions(query):
    assert request_constraints({'query': query}) == {}


def test_customer_body_not_wrapper_instructions_controls_scope_and_offsets():
    query = 'Customer wrote: "Which languages support text instructions?" Include our voice-navigation playbook.'
    constraint = request_constraints({'query': query})['instruction_modality']
    assert constraint.value['value'] == 'text'
    assert query[constraint.start:constraint.end] == constraint.evidence == 'text'


def test_assistant_claims_are_excluded_and_new_task_does_not_inherit_scope():
    enquiry = {'query': 'New question: which languages are supported?', 'history': [
        {'role': 'user', 'text': 'Which languages support voice instructions?'},
        {'role': 'assistant', 'text': 'You require text instructions.'},
    ]}
    before = deepcopy(enquiry)
    assert request_constraints(enquiry) == {}
    assert enquiry == before


def test_last_explicit_request_option_wins_within_the_active_task():
    enquiry = {'query': 'Actually, compare written instructions instead.', 'history': [
        {'role': 'user', 'text': 'Compare voice navigation instructions.'},
    ]}
    constraints = request_constraints(enquiry)
    # The correction stays customer-authored; an assistant cannot choose this value.
    assert constraints['instruction_modality'].value['value'] == 'text'
