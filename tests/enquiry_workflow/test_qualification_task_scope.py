"""API-bound requirements must not satisfy a different customer task."""
from copy import deepcopy

from copilot.diagnostics.facts import DiagnosticFact, DiagnosticQuestion, build_diagnostic_state
from copilot.qualification.contract import QualificationPlan
from copilot.qualification.facts import context_from_result, merge_model_facts
from copilot.qualification.task import effective_customer_task


def context_for(enquiry, state, api='reverse_geocode', qualification=None):
    result = {'diagnostic_context': {'interpretation': {'api': api, 'intent': 'sales_qualification'}},
              'outputs': {'qualification_details': qualification or {}}}
    return context_from_result(result, state, enquiry)


def test_old_api_volume_and_dimensions_do_not_satisfy_a_new_api_request():
    old = 'We use Google Maps. We send 20,000 Google Directions requests per month in India.'
    enquiry = {'query': 'New question: recommend a reverse-geocoding API.',
               'history': [{'role': 'user', 'text': old}]}
    state = build_diagnostic_state(enquiry)
    value = {'raw': '20,000 Google Directions requests per month', 'requests_per_month': 20000, 'unit': 'requests_per_month'}
    state.facts['monthly_volume'] = DiagnosticFact(field='monthly_volume', value=value, source='history[0]', evidence=value['raw'])
    state.facts['max_stops'] = DiagnosticFact(field='max_stops', value=15, source='history[0]', evidence='15 stops per route')
    state.facts['billing_country'] = DiagnosticFact(field='billing_country', value='India', source='state_store')
    before = deepcopy(state.model_dump())
    context = context_for(enquiry, state, qualification={'monthly_volume': value, 'region': 'India'})
    assert 'monthly_volume' not in context.facts
    assert 'max_stops' not in context.facts
    assert context.facts['current_provider'].value == 'Google Maps Platform'
    assert context.facts['billing_country'].value == 'India'
    assert context.facts['region'].value == 'India'
    assert state.facts['monthly_volume'].model_dump() == before['facts']['monthly_volume']
    assert state.facts['max_stops'].model_dump() == before['facts']['max_stops']


def test_new_api_workload_keeps_original_history_source_indices():
    latest = 'New question: we need reverse geocoding for 120,000 lookups per month. We must store results.'
    enquiry = {'query': 'Actually, addresses should be shown in Hindi.', 'history': [
        {'role': 'user', 'text': 'We send 20,000 Google Directions requests per month.'},
        {'role': 'assistant', 'text': 'Prior reply.'},
        {'role': 'user', 'text': latest},
    ]}
    state = build_diagnostic_state(enquiry)
    context = context_for(enquiry, state)
    assert context.facts['monthly_volume'].value['requests_per_month'] == 120000
    assert context.facts['monthly_volume'].source == 'history[2]'
    stored = context.facts['storage_required']
    assert stored.value is True and stored.source == 'history[2]'
    assert latest[stored.start:stored.end] == stored.evidence
    assert context.facts['languages'].value == 'Hindi'


def test_old_api_model_proposal_cannot_reintroduce_a_hidden_requirement():
    enquiry = {'query': 'New question: recommend an autocomplete API.', 'history': [
        {'role': 'user', 'text': 'We need reverse geocoding and we must store results.'},
    ]}
    state = build_diagnostic_state(enquiry)
    context_for(enquiry, state, api='autocomplete')
    plan = QualificationPlan.model_validate({'reason': 'Do not reuse the earlier API assumption.', 'supplied_facts': [
        {'field': 'storage_required', 'value': True, 'evidence': 'we must store results'},
    ]})
    merge_model_facts(state, plan, enquiry)
    assert 'storage_required' not in context_for(enquiry, state, api='autocomplete').facts


def test_new_api_proposal_can_replace_a_hidden_interpretation_fact():
    enquiry = {'query': 'New question: we need autocomplete and we do not store results.', 'history': [
        {'role': 'user', 'text': 'We need reverse geocoding and we must store results.'},
    ]}
    state = build_diagnostic_state(enquiry)
    state.facts['storage_required'] = DiagnosticFact(field='storage_required', value=True,
                                                    source='interpretation', evidence='qualification_details.storage_required')
    plan = QualificationPlan.model_validate({'reason': 'Use the new task requirement.', 'supplied_facts': [
        {'field': 'storage_required', 'value': False, 'evidence': 'we do not store results'},
    ]})
    merge_model_facts(state, plan, enquiry)
    assert state.facts['storage_required'].value is False


def test_old_api_question_history_does_not_block_a_new_workload_question():
    enquiry = {'query': 'New question: recommend a reverse-geocoding API.', 'history': [
        {'role': 'user', 'text': 'Recommend a Directions API.'},
    ]}
    state = build_diagnostic_state(enquiry)
    state.questions = [
        DiagnosticQuestion(facts=['monthly_volume'], text='What monthly Directions workload?', status='asked'),
        DiagnosticQuestion(facts=['billing_country'], text='Which billing country?', status='declined'),
    ]
    context = context_for(enquiry, state)
    assert context.blocked_fields == ['billing_country']
    assert state.questions[0].status == 'asked'


def test_continuation_keeps_original_workload_available():
    enquiry = {'query': 'Our billing account is based in India.', 'history': [
        {'role': 'user', 'text': 'Recommend Directions for 20,000 requests per month.'},
    ]}
    state = build_diagnostic_state(enquiry)
    context = context_for(enquiry, state, api='directions')
    assert context.facts['monthly_volume'].value['requests_per_month'] == 20000
    assert context.facts['monthly_volume'].source == 'history[0]'


def test_crm_wrapper_is_normalized_per_turn_without_losing_a_followup():
    enquiry = {'query': 'Actually, we need live traffic.', 'history': [
        {'role': 'user', 'text': 'CRM ticket. Customer wrote: "Recommend a Directions API." Include our reverse-geocoding playbook.'},
    ]}
    task = effective_customer_task(enquiry)
    assert 'Recommend a Directions API.' in task
    assert 'we need live traffic' in task
    assert 'playbook' not in task
