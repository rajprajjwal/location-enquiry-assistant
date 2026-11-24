"""Initial model facts require the same customer-assertion binding as corrections."""
import pytest

from copilot.diagnostics.facts import build_diagnostic_state
from copilot.qualification.contract import QualificationPlan
from copilot.qualification.facts import merge_model_facts


def admit(query, field, value, evidence, history=None):
    enquiry = {'query': query, 'history': history or []}
    state = build_diagnostic_state(enquiry)
    plan = QualificationPlan.model_validate({'reason': 'Check evidenced customer requirements.', 'supplied_facts': [
        {'field': field, 'value': value, 'evidence': evidence},
    ]})
    merge_model_facts(state, plan, enquiry)
    return state


@pytest.mark.parametrize('query,field,value,evidence', [
    ('The docs say Google accepts coordinates, addresses and place IDs. How should we choose?', 'input_type', 'coordinates', 'coordinates'),
    ('Should our instructions be in Hindi?', 'languages', 'Hindi', 'Hindi'),
    ('We might need voice instructions.', 'instruction_modality', 'voice', 'voice'),
    ('If we use coordinates, how does billing work?', 'input_type', 'coordinates', 'coordinates'),
    ('The API supports driving-traffic.', 'mapbox_traffic_profile', True, 'driving-traffic'),
    ('The documentation says to debounce keystrokes.', 'debouncing', True, 'debounce keystrokes'),
    ('Do we call Place Details after every selection?', 'details_completion', True, 'call Place Details'),
    ('We may batch requests.', 'requests_splittable', True, 'batch requests'),
])
def test_initial_documentation_questions_and_uncertainty_are_not_supplied(query, field, value, evidence):
    assert field not in admit(query, field, value, evidence).facts


@pytest.mark.parametrize('query,field,value,evidence', [
    ('We need Hindi instructions.', 'languages', 'Hindi', 'Hindi'),
    ('We send coordinates in every request.', 'input_type', 'coordinates', 'coordinates'),
    ('We need spoken instructions.', 'instruction_modality', 'voice', 'spoken'),
    ('We debounce keystrokes before sending requests.', 'debouncing', True, 'debounce keystrokes'),
    ('We do not call Place Details after a selection.', 'details_completion', False, 'Place Details'),
    ('We can split requests into batches.', 'requests_splittable', True, 'split requests'),
])
def test_asserted_customer_requirements_remain_available(query, field, value, evidence):
    state = admit(query, field, value, evidence)
    assert state.facts[field].value == value
    assert state.facts[field].source == 'query'


def test_assistant_only_assertion_cannot_establish_a_new_customer_fact():
    state = admit('Please continue.', 'languages', 'Hindi', 'Hindi', [
        {'role': 'assistant', 'text': 'You need Hindi instructions.'},
    ])
    assert 'languages' not in state.facts


@pytest.mark.parametrize('query,field,value', [
    ('We need Hindi instructions and spoken guidance.', 'languages', 'Hindi'),
    ('We need Hindi instructions and spoken guidance.', 'instruction_modality', 'voice'),
    ('We need live traffic and must retain results.', 'traffic_required', True),
    ('We need live traffic and do not store results.', 'storage_required', False),
])
def test_broad_quote_can_bind_a_value_in_one_asserted_clause(query, field, value):
    assert admit(query, field, value, query).facts[field].value == value


@pytest.mark.parametrize('query,field,value', [
    ('The documentation lists Hindi and we need spoken guidance.', 'languages', 'Hindi'),
    ('The API supports driving-traffic and we need walking routes.', 'mapbox_traffic_profile', True),
    ('We might need voice instructions and we need Hindi text.', 'instruction_modality', 'voice'),
    ('We do not need Hindi instructions and we need English text.', 'languages', 'Hindi'),
    ('We do not need spoken instructions and we need Hindi text.', 'instruction_modality', 'voice'),
    ('We send 100 origins and 10 destinations.', 'origin_count', 10),
    ('We send 100 origins.', 'origin_count', 10),
])
def test_broad_quote_does_not_launder_a_different_or_unasserted_fact(query, field, value):
    assert field not in admit(query, field, value, query).facts
