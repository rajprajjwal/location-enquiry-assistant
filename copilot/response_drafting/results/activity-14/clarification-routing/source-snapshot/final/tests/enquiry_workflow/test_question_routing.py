"""Keep requested checklists and provider documentation out of unrelated intake."""
from contextlib import closing
import json
from unittest.mock import Mock

from copilot.case_storage import cases
from copilot.case_storage.db import connect
from copilot.enquiry_interpretation import interpret
from copilot.enquiry_workflow.cases import run_case
from copilot.enquiry_workflow.routing import documentation_providers
from copilot.enquiry_workflow.workflow import run_enquiry
from copilot.registered_tools.tool_registry import DocumentSearchTool
from copilot.response_drafting.schemas import validate_outputs
from tests.support.helpers import ScriptedClient, completion, model_json

DOC_QUERY = ('What do Google Reverse Geocoding, Nominatim Reverse, Ola Reverse Geocode, '
             'and Mapbox Geocoding document about language and address details?')
CHECK_QUERY = ('A dispatch-tool prospect needs driver-to-job ETAs. '
               'What should we ask before recommending a distance-matrix API?')


def client(intent='docs_how_to', api='reverse_geocode'):
    def respond(messages, **_options):
        try:
            payload = json.loads(messages[-1]['content'])
        except ValueError:
            payload = {}
        if payload.get('qualification_plan'):
            return completion('{"supplied_facts":[],"groups":[],"reason":"Use the applicable missing requirements."}')
        if 'passages' in payload:
            return completion('{"passages":[1]}')
        if 'candidate' in payload:
            return completion('{"answers_enquiry":true}')
        return completion(model_json(intent=intent, api=api, team='Sales' if intent == 'sales_qualification' else 'Support'))
    result = Mock()
    result.complete.side_effect = respond
    return result


def search(calls, missing=()):
    def retrieve(query):
        provider = query.split(' ', 1)[0]
        calls.append(query)
        if provider in missing:
            return []
        return [{'source_url': 'https://example.com/' + provider,
                 'relevant_passage': f'{provider} test reference: request language and address details.'}]
    return DocumentSearchTool(search_function=retrieve)


def test_checklist_is_an_answer_without_an_operating_region_pending_reply(tmp_path):
    path = tmp_path / 'checklist.db'
    with closing(connect(path)) as con:
        result = run_case(con, CHECK_QUERY, client=client('sales_qualification', 'distance_matrix'), search=search([]))
        cid = result['case_id']
        assert result['status'] == 'final', result['critic']
        assert result['clarifying_questions']['questions'] == []
        assert cases.load_state(con, cid)['pending_clarification'] is None
        text = result['response_draft']['draft_text']
        assert 'origins' in text and 'destinations' in text
        assert all(q['field'] != 'region' for q in result['outputs']['clarifying_questions']['questions'])
        assert result['outputs']['next_action']['action_type'] != 'ask_clarifying_questions'
        assert not validate_outputs(result['outputs'])
    with closing(connect(path)) as con:
        assert cases.load_state(con, cid)['pending_clarification'] is None
        assert not [m for m in cases.get_case_history(con, cid) if m['role'] == 'clarification']


def test_ordinary_recommendation_still_uses_missing_customer_intake():
    query = 'Recommend a distance-matrix provider for our dispatch tool.'
    enquiry = {'query': query}
    interpretation = interpret(enquiry, client=ScriptedClient([completion(model_json(intent='sales_qualification', api='distance_matrix', team='Sales'))]))
    result = run_enquiry(enquiry, interpretation, client=client('sales_qualification', 'distance_matrix'), search=search([]))
    assert result['status'] == 'clarification_needed'
    assert result['clarifying_questions']['questions'][0]['field'] == 'region'


def test_four_provider_document_request_searches_every_target_without_single_provider_intake(tmp_path):
    calls = []
    with closing(connect(tmp_path / 'docs.db')) as con:
        result = run_case(con, DOC_QUERY, client=client(), search=search(calls))
        assert result['status'] == 'final', result['critic']
        assert result['clarifying_questions']['questions'] == []
        assert result['outputs']['clarifying_questions']['questions'] == []
        assert cases.load_state(con, result['case_id'])['pending_clarification'] is None
        assert set(result['outputs']['comparison']['providers']) == {'Google Maps Platform', 'OSM Nominatim', 'Ola Maps', 'Mapbox'}
        assert len(calls) == len(result['response_draft']['citations']) == 4
        assert result['step_count'] <= 10
        assert not validate_outputs(result['outputs'])


def test_missing_provider_evidence_is_explicit_without_reusing_other_provider_quotes(tmp_path):
    with closing(connect(tmp_path / 'partial.db')) as con:
        result = run_case(con, DOC_QUERY, client=client(), search=search([], missing={'OSM'}))
        assert result['status'] == 'final'
        text = result['response_draft']['draft_text']
        assert 'OSM Nominatim: No answer could be verified' in text
        assert result['outputs']['comparison']['notes'] == 'Some providers lack verified evidence.'
        assert len(result['response_draft']['citations']) == 3


def test_documentation_scope_does_not_capture_price_or_single_provider_requests():
    assert documentation_providers(DOC_QUERY)
    assert not documentation_providers('What do Google and Mapbox charge per month?')
    assert not documentation_providers('How do I set Mapbox language?')
    assert not documentation_providers('We may use Google or Mapbox. How do I set language?')


def test_reopening_an_old_region_intake_clears_the_pending_checklist_question(tmp_path):
    with closing(connect(tmp_path / 'old-checklist.db')) as con:
        cid = cases.create_case(con)
        cases.add_message(con, cid, 'user', CHECK_QUERY)
        state = cases.load_state(con, cid)
        state['pending_clarification'] = {'field': 'region', 'task': CHECK_QUERY}
        cases.save_state(con, cid, state)
        result = run_case(con, 'Germany', case_id=cid,
                          client=client('sales_qualification', 'distance_matrix'), search=search([]))
        assert result['status'] == 'final', result['critic']
        assert result['clarifying_questions']['questions'] == []
        assert cases.load_state(con, cid)['pending_clarification'] is None


def test_reopening_an_old_provider_question_keeps_the_explicit_comparison_scope(tmp_path):
    with closing(connect(tmp_path / 'old-docs.db')) as con:
        cid = cases.create_case(con)
        cases.add_message(con, cid, 'user', DOC_QUERY)
        state = cases.load_state(con, cid)
        state['pending_clarification'] = {'field': 'provider', 'task': DOC_QUERY}
        cases.save_state(con, cid, state)
        result = run_case(con, 'Mapbox', case_id=cid, client=client(), search=search([]))
        assert result['status'] == 'final', result['critic']
        assert len(result['outputs']['comparison']['providers']) == 4
        assert cases.load_state(con, cid)['pending_clarification'] is None


def test_incidental_provider_history_does_not_become_a_document_comparison_target():
    assert not documentation_providers('What does Google return for a failed reverse-geocoding request? We used Mapbox earlier.')
    assert set(documentation_providers('We used Nominatim earlier. Compare Google and Mapbox documentation on language.')) == {'Google Maps Platform', 'Mapbox'}


def test_requested_checklist_does_not_swallow_an_additional_document_comparison(tmp_path):
    query = CHECK_QUERY + ' Also compare Google and Mapbox documentation on coverage.'
    with closing(connect(tmp_path / 'mixed.db')) as con:
        result = run_case(con, query, client=client('sales_qualification', 'distance_matrix'), search=search([]))
        assert result['status'] == 'final', result['critic']
        assert result['outputs']['comparison']['providers'] == ['Google Maps Platform', 'Mapbox']
        assert not any(step['action'] == 'qualification_checklist' for step in result['steps'])
