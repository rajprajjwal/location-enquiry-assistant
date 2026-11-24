"""Read-only ownership/qualification integration probes with temporary case stores."""
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
from copilot.enquiry_workflow.ownership_status import review_customer_status
from copilot.registered_tools.tool_registry import DocumentSearchTool
from tests.enquiry_workflow.test_escalation import parsed_for
from tests.support.helpers import completion


def probe():
    query = 'How do I set waypoints in Mapbox Directions?'
    parsed = parsed_for(query, 'docs_how_to')
    status = []
    for question in ('Are you an existing customer?', 'Are you already using this service?',
                     'Are you a new or existing customer?'):
        for answer in ('yes', 'no', 'existing', 'new', "Let's leave that open for now."):
            resolved, deferred = review_customer_status(answer, [{'role': 'assistant', 'text': question}], parsed)
            status.append({'question': question, 'answer': answer, 'status': resolved, 'deferred': deferred})
    client = Mock()
    client.complete.return_value = completion('{"passages":[1],"answers_enquiry":true}')
    search = DocumentSearchTool(search_function=lambda _: [
        {'source_url': 'https://example.test/waypoints',
         'relevant_passage': 'Add intermediate locations in the waypoints field.'},
    ])
    pending = []
    with TemporaryDirectory() as directory, patch.object(service, 'interpret', lambda *a, **kw: parsed), patch.object(
        service, 'add_follow_up_questions', lambda result, *a, **kw: result
    ):
        for answer in ('existing', 'new'):
            with closing(connect(Path(directory) / (answer + '.db'))) as con:
                cid = cases.create_case(con)
                cases.add_message(con, cid, 'user', query)
                cases.add_message(con, cid, 'clarification', 'Are you a new or existing customer?')
                cases.save_state(con, cid, {'pending_clarification': {'field': 'customer_status', 'task': query}})
                result = service.run_case(con, answer, case_id=cid, client=client, search=search, diagnostic_planning=False)
                pending.append({
                    'answer': answer, 'returned_status': result['ownership_review']['customer_status'],
                    'persisted_status': result['conversation_state']['ownership_status'].get('customer_status'),
                    'owner': result['outputs']['responsible_role']['owner'],
                    'provisional': result['ownership_review']['provisional'], 'route': result['status'],
                    'pending_reply': cases.load_state(con, cid).get('pending_clarification'),
                })
    return {'status_replies': status, 'pending_status_reply': pending, 'live_model_calls': 0}


if __name__ == '__main__':
    print(json.dumps(probe(), indent=2))
