"""Keep customer corrections newer than the facts they replace."""
from types import SimpleNamespace

import pytest

from copilot.diagnostics.facts import DiagnosticFact, build_diagnostic_state
from copilot.qualification.contract import QualificationPlan
from copilot.qualification.facts import merge_model_facts


def plan(field, value, evidence):
    return QualificationPlan.model_validate({
        'reason': 'Use the explicitly supplied customer requirement.',
        'supplied_facts': [{'field': field, 'value': value, 'evidence': evidence}],
    })


def test_current_assertion_corrects_a_saved_model_fact_after_reopening():
    first = {'query': 'We need English instructions.'}
    state = build_diagnostic_state(first)
    merge_model_facts(state, plan('languages', 'English', 'English'), first)
    enquiry = {'query': 'Actually we need Hindi instructions.', 'history': [
        {'role': 'user', 'text': first['query']},
        {'role': 'assistant', 'text': 'You require French.'},
    ]}
    state = build_diagnostic_state(enquiry, state.model_dump(mode='json'))

    merge_model_facts(state, plan('languages', 'Hindi', 'Hindi'), enquiry)

    assert state.facts['languages'].value == 'Hindi'
    assert state.facts['languages'].source == 'query'
    assert state.facts['languages'].evidence == 'Hindi'


def test_newer_history_assertion_corrects_an_older_supplied_fact():
    enquiry = {'query': 'Please proceed.', 'history': [
        {'role': 'user', 'text': 'We need English instructions.'},
        {'role': 'assistant', 'text': 'You require French.'},
        {'role': 'user', 'text': 'Actually we need Hindi instructions.'},
    ]}
    state = build_diagnostic_state(enquiry)
    state.facts['languages'] = DiagnosticFact(
        field='languages', value='English', source='query', evidence='English')

    merge_model_facts(state, plan('languages', 'Hindi', 'Hindi'), enquiry)

    assert state.facts['languages'].value == 'Hindi'
    assert state.facts['languages'].source == 'history[2]'


def test_stale_history_proposal_cannot_replace_a_current_customer_fact():
    enquiry = {'query': 'Actually we need Hindi instructions.', 'history': [
        {'role': 'user', 'text': 'We need English instructions.'},
    ]}
    state = build_diagnostic_state(enquiry)
    merge_model_facts(state, plan('languages', 'Hindi', 'Hindi'), enquiry)

    merge_model_facts(state, plan('languages', 'English', 'English'), enquiry)

    assert state.facts['languages'].value == 'Hindi'
    assert state.facts['languages'].source == 'query'


def test_same_turn_deterministic_fact_remains_authoritative():
    enquiry = {'query': 'Instructions are shown in English; Hindi is an alternative.'}
    state = build_diagnostic_state(enquiry)
    state.facts['languages'] = DiagnosticFact(
        field='languages', value='English', source='query', evidence='shown in English',
        start=17, end=33)

    merge_model_facts(state, plan('languages', 'Hindi', 'Hindi'), enquiry)

    assert state.facts['languages'].value == 'English'


def test_same_turn_validated_interpretation_remains_authoritative():
    enquiry = {'query': 'Hindi instructions are one option.'}
    state = build_diagnostic_state(enquiry)
    state.facts['languages'] = DiagnosticFact(
        field='languages', value='English', source='interpretation',
        evidence='qualification_details.languages')

    merge_model_facts(state, plan('languages', 'Hindi', 'Hindi'), enquiry)

    assert state.facts['languages'].value == 'English'


@pytest.mark.parametrize('query', [
    'Do we need Hindi instructions?',
    'We might need Hindi instructions.',
    'If we need Hindi instructions, what changes?',
    'The provider documentation lists Hindi instructions.',
])
def test_unasserted_or_documentation_mention_cannot_correct_a_customer_fact(query):
    enquiry = {'query': query, 'history': [
        {'role': 'user', 'text': 'We need English instructions.'},
    ]}
    state = build_diagnostic_state(enquiry)
    state.facts['languages'] = DiagnosticFact(
        field='languages', value='English', source='query', evidence='English')

    merge_model_facts(state, plan('languages', 'Hindi', 'Hindi'), enquiry)

    assert state.facts['languages'].value == 'English'


def test_new_explicit_boolean_assertion_can_correct_a_previous_false_value():
    enquiry = {'query': 'We need live traffic.', 'history': [
        {'role': 'user', 'text': 'We do not need live traffic.'},
    ]}
    state = build_diagnostic_state(enquiry)
    state.facts['traffic_required'] = DiagnosticFact(
        field='traffic_required', value=False, source='history[0]',
        evidence='We do not need live traffic.')

    merge_model_facts(state, plan('traffic_required', True, 'We need live traffic.'), enquiry)

    assert state.facts['traffic_required'].value is True


def test_assistant_only_evidence_cannot_replace_a_customer_fact():
    enquiry = {'query': 'Please proceed.', 'history': [
        {'role': 'user', 'text': 'We need English instructions.'},
        {'role': 'assistant', 'text': 'Use Hindi.'},
    ]}
    state = build_diagnostic_state(enquiry)
    state.facts['languages'] = DiagnosticFact(
        field='languages', value='English', source='history[0]', evidence='English')

    merge_model_facts(state, plan('languages', 'Hindi', 'Hindi'), enquiry)

    assert state.facts['languages'].value == 'English'


@pytest.mark.parametrize('evidence', ['', ' ', '\n'])
def test_blank_evidence_never_binds_even_at_the_merge_boundary(evidence):
    enquiry = {'query': 'We need Hindi instructions.'}
    state = build_diagnostic_state(enquiry)
    proposal = SimpleNamespace(field='languages', value='Hindi', evidence=evidence)

    merge_model_facts(state, SimpleNamespace(supplied_facts=[proposal]), enquiry)

    assert 'languages' not in state.facts
