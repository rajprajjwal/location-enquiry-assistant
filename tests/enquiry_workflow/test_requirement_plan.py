"""One resolved plan must drive question rendering and final checklist advice."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

from copilot.diagnostics.facts import DiagnosticFact, build_diagnostic_state
from copilot.qualification.contract import QualificationContext, QualificationPlan
from copilot.qualification.decisions import requirement_plan
from copilot.qualification.extraction import extract_requirements
from copilot.qualification.facts import merge_model_facts
from copilot.qualification.finalization import finalize_requirements
from copilot.qualification.requirements import applicable_groups
from copilot.qualification.planning import plan_qualification
from tests.enquiry_workflow.test_qualification import result_for


def test_unselected_conditional_decision_does_not_become_a_question():
    context = QualificationContext(api='reverse_geocode', intent='pricing_quote')
    candidate = [{'fields': ['storage_required'], 'decision_impact': 'Storage affects licensing.'}]
    plan = requirement_plan(context, build_diagnostic_state({'query':'Price a lookup.'}), candidate,
                            'Price a lookup.', selected_fields=set())
    assert plan.decisions == []
    assert plan.omitted


def test_selected_decision_keeps_every_independently_missing_field():
    context = QualificationContext(api='directions', intent='capability_match')
    candidate = [{'fields': ['hazmat_required','vehicle_dimensions'], 'decision_impact':'Vehicle restrictions affect fit.'}]
    plan = requirement_plan(context, build_diagnostic_state({'query':'We route trucks.'}), candidate,
                            'We route trucks.', selected_fields={'hazmat_required'})
    assert plan.decisions[0].fields == ['hazmat_required','vehicle_dimensions']


def test_matrix_quantity_statistics_and_periods_are_separate():
    enquiry = {'query':'We need typical 8 origins and maximum 40 origins. We need typical 6 destinations and maximum 30 destinations. We compute 100 matrices per hour and 20,000 matrices per month.'}
    facts = {fact['field']:fact['value'] for fact in extract_requirements(enquiry)}
    assert facts['typical_origin_count'] == 8
    assert facts['maximum_origin_count'] == 40
    assert facts['typical_destination_count'] == 6
    assert facts['maximum_destination_count'] == 30
    assert facts['matrices_per_hour'] == 100
    assert facts['matrices_per_month'] == 20000


def test_a_typical_count_cannot_supply_a_maximum_count():
    enquiry = {'query':'We need typical 10 origins, with maximum 100 origins.'}
    state = build_diagnostic_state(enquiry)
    plan = QualificationPlan.model_validate({'reason':'Keep statistic scope.', 'supplied_facts':[
        {'field':'maximum_origin_count','value':10,'evidence':enquiry['query']}]})
    merge_model_facts(state,plan,enquiry)
    assert 'maximum_origin_count' not in state.facts


def test_matrix_checklist_covers_named_workload_shape_and_conditions():
    context = QualificationContext(api='distance_matrix', intent='sales_qualification')
    enquiry = {'query':'Before choosing a matrix service, what workload and matrix-size requirements should we clarify, including traffic and departure times?'}
    groups = applicable_groups(context,enquiry,{})
    fields = {field for group in groups for field in group['fields']}
    assert {'typical_origin_count','maximum_origin_count','typical_destination_count','maximum_destination_count',
            'matrices_per_hour','matrices_per_month','peak_concurrency','traffic_conditions','departure_time_mode','requests_splittable'} <= fields


def test_provider_neutral_checklist_does_not_ask_for_a_vendor_profile():
    context = QualificationContext(api='distance_matrix', intent='sales_qualification')
    groups = applicable_groups(context,{'query':'What should we ask before recommending a matrix API?'},{})
    assert not any('mapbox_traffic_profile' in group['fields'] for group in groups)


def test_geographic_capacity_question_selects_matching_behavior_with_inflected_restriction():
    context = QualificationContext(api='autocomplete', intent='coverage_limits')
    enquiry = {'query':'Can autocomplete be restricted to several countries in one request?'}
    groups = applicable_groups(context, enquiry, {})
    assert [group['fields'] for group in groups] == [['geographic_matching']]


def test_geographic_configuration_instructions_do_not_request_unrelated_poi_requirements():
    context = QualificationContext(api='autocomplete', intent='docs_how_to')
    enquiry = {'query':'How do we restrict autocomplete results to our country on each provider?'}
    groups = applicable_groups(context, enquiry, {})
    assert [group['fields'] for group in groups] == [['geographic_matching']]
    assert not groups[0]['required']


def test_licensing_restrictions_are_not_geographic_filters():
    context = QualificationContext(api='autocomplete', intent='docs_how_to')
    enquiry = {'query':'What licensing restrictions apply to Google Autocomplete results?'}
    assert applicable_groups(context, enquiry, {}) == []


def test_a_named_provider_quote_does_not_require_an_unrelated_provider_account():
    context = QualificationContext(api='directions', intent='pricing_quote', assumptions={
        'monthly_volume': DiagnosticFact(field='monthly_volume', value={'unit':'requests_per_month','requests_per_month':400000})})
    enquiry = {'query':'What would 400,000 Mapbox Directions requests a month cost for driving routes?'}
    assert applicable_groups(context, enquiry, {}) == []


def test_a_named_provider_recommendation_only_checks_that_providers_eligibility():
    context = QualificationContext(api='directions', intent='capability_match')
    groups = applicable_groups(context, {'query':'What do you recommend for our Ola Directions setup?'}, {})
    fields = {field for group in groups for field in group['fields']}
    assert 'existing_project' not in fields
    assert 'ola_contract' in fields


def test_priced_matrix_elements_do_not_require_address_representation_to_calculate_cost():
    from copilot.qualification.workload import from_text
    query = 'Our workload is 180,000 traffic-aware Distance Matrix elements a month. Estimate the Google price.'
    volume = from_text(query)
    assert volume['unit'] == 'elements_per_month'
    assert volume['requests_per_month'] == 180000
    context = QualificationContext(api='distance_matrix', intent='pricing_quote', facts={
        'monthly_volume':DiagnosticFact(field='monthly_volume', value=volume)})
    assert applicable_groups(context, {'query':query}, {}) == []


def test_details_lookup_price_does_not_require_autocomplete_keystroke_conversion():
    context = QualificationContext(api='autocomplete', intent='pricing_quote')
    enquiry = {'query':'Ola Place Details after autocomplete selection: 120,000 calls a month. Cost?'}
    assert applicable_groups(context, enquiry, {}) == []


def test_autocomplete_request_counts_do_not_require_keystroke_conversion():
    context = QualificationContext(api='autocomplete', intent='pricing_quote')
    enquiry = {'query':'Google Autocomplete Legacy: 90,000 sessions with 6 requests each. Cost?'}
    fields = {field for group in applicable_groups(context, enquiry, {}) for field in group['fields']}
    assert 'details_completion' in fields
    assert 'debouncing' not in fields


def test_non_google_autocomplete_quote_does_not_ask_about_place_details():
    context = QualificationContext(api='autocomplete', intent='pricing_comparison')
    enquiry = {'query':'Ola vs Mapbox autocomplete for 90,000 sessions with 6 keystrokes each. Cost?'}
    fields = {field for group in applicable_groups(context, enquiry, {}) for field in group['fields']}
    assert fields == {'debouncing'}


def test_requirement_decisions_and_final_advice_are_identical_without_control_changes():
    enquiry = {'query':'What should we ask before recommending a reverse-geocoding API?'}
    original = result_for(enquiry)
    original['diagnostic_context']['interpretation']['api']='reverse_geocode'
    client = Mock()
    client.complete.return_value = SimpleNamespace(finish_reason='stop',text=json.dumps({'supplied_facts':[], 'groups':[], 'reason':'Cover the requested requirements.'}))
    selected = plan_qualification(original,enquiry,client=client)
    # Use a complete production output envelope for final schema validation.
    from copilot.enquiry_interpretation.postcheck import rules_only
    from copilot.enquiry_interpretation.seam import models
    from copilot.response_drafting.drafter import build_support_output
    interpreted = models().InterpretationOutput.model_validate(rules_only(query=enquiry['query'], abstain_reason='no_rule_match')['output'])
    draft = {'draft_text':'Reference guidance.', 'citations':[], 'is_refusal':False, 'refusal':None}
    selected['outputs'] = {**build_support_output(draft,interpreted,enquiry['query']),
                           'clarifying_questions':selected['outputs']['clarifying_questions']}
    selected['response_draft']=draft
    before=deepcopy(selected)
    actual = finalize_requirements(selected,enquiry)
    assert actual['final_validation']['valid']
    for decision in actual['requirement_plan']['decisions']:
        assert decision['question'] in actual['response_draft']['draft_text']
    for field in ['status','pending_reply','clarifying_questions']:
        assert actual[field] == before[field]
    for field in ['responsible_role','next_action','proposed_record_update']:
        assert actual['outputs'][field] == before['outputs'][field]
    assert finalize_requirements(actual,enquiry)['response_draft'] == actual['response_draft']
