"""Local integration checks using synthetic enquiries and temporary case stores."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
import json
import sys

REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')
sys.path.insert(0, str(REPO))
from copilot.case_storage import cases
from copilot.case_storage.db import connect
from copilot.enquiry_workflow import cases as service
from copilot.enquiry_workflow.ownership_status import review_customer_status, customer_status_reply
from copilot.registered_tools.tool_registry import DocumentSearchTool
from tests.enquiry_workflow.test_escalation import parsed_for
from tests.support.helpers import completion


def probe():
    query = 'How do I set waypoints in Mapbox Directions?'
    parsed = parsed_for(query, 'docs_how_to')
    replies = []
    for question in ('Are you an existing customer?', 'Are you already using this service?',
                     'Are you a new or existing customer?'):
        for answer in ('yes', 'no', 'existing', 'new', "Let's leave that open for now."):
            status, deferred = review_customer_status(answer, [{'role': 'assistant', 'text': question}], parsed)
            replies.append({'question': question, 'answer': answer, 'status': status, 'deferred': deferred})
    client = Mock()
    client.complete.return_value = completion('{"passages":[1],"answers_enquiry":true}')
    search = DocumentSearchTool(search_function=lambda _: [
        {'source_url': 'https://example.test/waypoints',
         'relevant_passage': 'Add intermediate locations in the waypoints field.'},
    ])
    pending = []
    scenarios = [
        (query, 'existing', 'docs_how_to'),
        (query, 'new', 'docs_how_to'),
        (query, 'new', 'docs_how_to', False),
        (query, 'existing', 'docs_how_to', False),
        (f'We are an existing customer. {query}', 'new', 'docs_how_to'),
        (f'We are a new customer. {query}', 'existing', 'docs_how_to'),
        ('Production is down. Directions returns HTTP 503 for every request.', 'new', 'troubleshooting'),
    ]
    with TemporaryDirectory() as directory, patch.object(service, 'add_follow_up_questions', lambda result, *a, **kw: result):
        for index, scenario in enumerate(scenarios):
            task, answer, intent, *assistant = scenario
            current = parsed_for(task, intent)
            with closing(connect(Path(directory) / f'{index}.db')) as con, patch.object(service, 'interpret', lambda *a, **kw: current):
                cid = cases.create_case(con)
                cases.add_message(con, cid, 'user', task)
                if not assistant or assistant[0]:
                    cases.add_message(con, cid, 'clarification', 'Are you a new or existing customer?')
                cases.save_state(con, cid, {'pending_clarification': {'field': 'customer_status', 'task': task}})
                result = service.run_case(con, answer, case_id=cid, client=client, search=search, diagnostic_planning=False)
                pending.append({
                    'restored_task': task, 'raw_reply': answer,
                    'assistant_question_saved': not assistant or assistant[0],
                    'returned_status': result['ownership_review']['customer_status'],
                    'persisted_status': result['conversation_state']['ownership_status'].get('customer_status'),
                    'owner': result['outputs']['responsible_role']['owner'],
                    'provisional': result['ownership_review']['provisional'], 'route': result['status'],
                    'pending_reply': cases.load_state(con, cid).get('pending_clarification'),
                    'approval_statuses': [item['status'] for item in cases.list_pending(con, cid)],
                })
    setup_guards = [
        {'question': question, 'answer': answer, 'bound': bound,
         'result': customer_status_reply(answer, question, bound=bound)}
        for question in ('Is this a new or existing Google Cloud project?',
                         'Is this a new or existing API key?',
                         'Is this a new or existing account setup?')
        for answer in ('new', 'existing') for bound in (False, True)
    ]
    return {'status_replies': replies, 'pending_status_reply': pending,
            'setup_question_guards': setup_guards, 'live_model_calls': 0}


if __name__ == '__main__':
    print(json.dumps(probe(), indent=2))
