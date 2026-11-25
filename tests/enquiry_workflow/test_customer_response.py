"""Customer presentation must preserve decisions, evidence and approval boundaries."""
from copy import deepcopy

import pytest

from copilot.response_drafting.customer_response import format_customer_response


def result(text='A supported answer.', *, citations=(), status='final', action=None):
    draft = {'draft_text': text, 'citations': list(citations), 'is_refusal': False, 'refusal': None}
    return {'status': status, 'response_draft': draft if status == 'final' else None,
            'clarifying_questions': {'needed': False, 'questions': []}, 'proposed_actions': [],
            'outputs': {'response_draft': draft, 'comparison': {'applicable': False, 'assumptions': []},
                        'clarifying_questions': {'needed': False, 'questions': []},
                        'responsible_role': {'owner': 'Support L2', 'severity': 'SEV2'},
                        'next_action': action or {'action_type': 'answer_directly', 'description': 'Review the drafted reply.'}}}


def citation(url='https://docs.example.com/api', span='A supported answer.'):
    return {'url': url, 'span': span, 'supports_claim': span}


def test_answer_and_sources_preserve_claims_without_mutating_workflow():
    original = result('A supported answer.\n\nAdditional verified detail.', citations=[citation()])
    before = deepcopy(original)
    response = format_customer_response(original)
    assert original == before
    assert [s['heading'] for s in response['sections']] == ['Answer', 'Key details', 'Sources']
    assert 'A supported answer. [1](https://docs.example.com/api)' in response['markdown']
    assert 'Additional verified detail.' in response['markdown']
    assert 'Support L2' not in response['markdown'] and 'SEV2' not in response['markdown']
    assert 'Review the drafted reply' not in response['markdown']


def test_clarification_uses_only_the_active_question_and_no_sources():
    original = result(status='clarification_needed', action={'action_type': 'ask_clarifying_questions'})
    original['clarifying_questions'] = {'needed': True, 'questions': [
        {'field': 'monthly_volume', 'text': 'How many requests do you expect each month?'}]}
    original['outputs']['clarifying_questions']['questions'] = [{'text': 'Who is the decision maker?'}]
    before = deepcopy(original)
    response = format_customer_response(original)
    assert original == before
    assert 'expected monthly request volume' in response['markdown']
    assert response['markdown'].count('How many requests do you expect each month?') == 1
    assert 'decision maker' not in response['markdown']
    assert 'Sources' not in [s['heading'] for s in response['sections']]


@pytest.mark.parametrize(('approval', 'executed', 'expected'), [
    ('pending', False, 'awaiting review'),
    ('pending', True, 'awaiting review'),
    ('approved', False, 'awaiting application'),
    ('approved', True, 'has been completed'),
    ('rejected', False, 'was not approved'),
])
def test_handoff_wording_follows_execution_and_approval(approval, executed, expected):
    response = format_customer_response(result(status='escalated', action={
        'action_type': 'propose_escalation', 'approval_status': approval, 'executed': executed}))
    assert expected in response['markdown']
    if not executed:
        assert 'has been completed' not in response['markdown']


def test_record_proposal_is_not_presented_as_a_completed_update():
    original = result(action={'action_type': 'propose_record_update', 'approval_status': 'pending', 'executed': False})
    original['outputs']['proposed_record_update'] = {'proposal': {
        'record_id': 'TKT-456', 'fields': {'status': 'Investigating'}}}
    response = format_customer_response(original)
    assert 'TKT-456' in response['markdown'] and 'Investigating' in response['markdown']
    assert 'awaiting review' in response['markdown'] and 'has not been carried out' in response['markdown']


def test_manual_review_does_not_expose_internal_failure_details():
    original = result(status='escalated', action={'action_type': 'refuse', 'description': 'Step limit reached: tool_timeout'})
    original['critic'] = {'reason': 'Planner schema failed at executor step 10'}
    response = format_customer_response(original)
    assert 'could not verify' in response['markdown']
    assert all(text not in response['markdown'] for text in ['schema failed', 'tool_timeout', 'Step limit'])


def test_failed_output_validation_cannot_be_presented_as_a_verified_answer():
    original = result('This answer failed final validation.', citations=[citation()])
    original['final_validation'] = {'valid': False, 'errors': ['Invalid output schema']}
    response = format_customer_response(original)
    assert 'This answer failed final validation.' not in response['markdown']
    assert 'could not verify' in response['markdown']
    assert '### Sources' not in response['markdown']


def test_sources_deduplicate_urls_and_remap_existing_references():
    response = format_customer_response(result('First claim [1]. Second claim [2].', citations=[
        citation(span='First claim'), citation(span='Second claim')]))
    assert response['markdown'].count('[1](https://docs.example.com/api)') == 3
    assert '[2]' not in response['markdown']
    assert len(response['sections']) == 2


def test_unsupported_source_schemes_are_not_rendered_as_links():
    response = format_customer_response(result(citations=[citation('javascript:alert(1)')]))
    assert 'javascript:' not in response['markdown']
    assert 'Sources' not in [s['heading'] for s in response['sections']]


def test_pricing_comparison_retains_usage_assumptions_and_citations():
    original = result('- Google Maps Platform: USD 12 [1]\n  Monthly usage: 30,000 requests.\n'
                      '- Mapbox: USD 18 [2]\nList prices exclude taxes.', citations=[
                          citation('https://developers.example.com/pricing'), citation('https://docs.example.com/pricing')])
    original['outputs']['comparison'] = {'applicable': True, 'dimensions': ['pricing'],
        'providers': ['Google Maps Platform', 'Mapbox'], 'assumptions': ['List prices exclude taxes.']}
    response = format_customer_response(original)
    assert '| Provider / scenario |' in response['markdown']
    assert 'USD 12' in response['markdown'] and 'USD 18' in response['markdown']
    assert '30,000 requests' in response['markdown']
    assert response['markdown'].count('List prices exclude taxes.') == 1
    assert [s['heading'] for s in response['sections']] == ['Answer', 'Key details', 'Assumptions / missing information', 'Sources']


def test_combined_comparison_keeps_unverified_coverage_and_scenario_conditions():
    original = result('Comparison for Directions in India.', citations=[citation()])
    original['outputs']['comparison'] = {'applicable': True, 'dimensions': ['pricing', 'limits', 'coverage'],
        'assumptions': ['Same monthly workload.'], 'provider_results': [
            {'provider': name,
             'pricing': {'status': 'verified', 'reason': None, 'estimates': [
                 {'scenario': 'Driving', 'currency': 'USD', 'monthly_cost': amount,
                  'source_references': [{'url': 'https://docs.example.com/api'}],
                  'assumptions': ['No traffic requested.']}]},
             'limits': {'status': 'verified', 'summary': 'Documented request cap.', 'findings': [{'url': 'https://docs.example.com/api'}]},
             'coverage': {'status': 'missing_evidence', 'reason': 'Standard driving coverage is not verified.'}}
            for name, amount in [('Google Maps Platform', '12'), ('Mapbox', '18')]]}
    response = format_customer_response(original)
    assert '| Provider | Estimated monthly cost | Limits | Coverage |' in response['markdown']
    assert 'Unverified: Standard driving coverage is not verified.' in response['markdown']
    assert 'Same monthly workload.' in response['markdown'] and 'No traffic requested.' in response['markdown']


def test_code_blocks_are_kept_whole_in_details():
    text = '```json\n{"coordinates": [1, 2]}\n\n```'
    response = format_customer_response(result(text))
    assert response['sections'][1]['content'] == text


def test_citation_numbers_do_not_rewrite_code_or_inline_arrays():
    text = 'Example: `[1]`.\n\n```json\n{"coordinates": [1]}\n```'
    response = format_customer_response(result(text, citations=[citation(span='[1]')]))
    assert '`[1]`' in response['markdown']
    assert '```json\n{"coordinates": [1]}\n```' in response['markdown']
