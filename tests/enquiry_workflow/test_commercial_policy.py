"""Explicit commercial decisions keep status provisional and actions unexecuted."""
from unittest.mock import patch

import pytest

from copilot.enquiry_workflow.escalation import route_enquiry, handoff_proposal
from tests.enquiry_workflow.test_escalation import parsed_for


@pytest.mark.parametrize(('query','intent'),[
    ('Quote Google Directions for 250,000 calls a month.','pricing_quote'),
    ('What licensing obligations apply when self-hosting a routing service?','docs_how_to'),
    ('Can we resell the geocoded results to other businesses?','docs_how_to'),
])
def test_explicit_commercial_work_gets_provisional_sales_without_a_handoff(query,intent):
    with patch('copilot.enquiry_workflow.escalation._model_category') as model:
        route=route_enquiry(query,parsed_for(query,intent))
    assert route['owner']=='Account team (Sales)'
    assert route['ownership_review']['customer_status']=='unknown'
    assert route['ownership_review']['provisional']
    assert not route['should_escalate'] and handoff_proposal(route) is None
    model.assert_not_called()


def test_existing_customer_technical_guidance_keeps_support():
    query='What licensing obligations apply to this API?'
    route=route_enquiry(query,parsed_for(query,'docs_how_to'),confirmed_customer_status='existing')
    assert route['owner']=='Support L1'
    assert not route['ownership_review']['provisional']


def test_published_arithmetic_is_not_automatically_a_deployment_quote():
    query='Calculate the published list-price charge for 250,000 Google Directions calls.'
    route=route_enquiry(query,parsed_for(query,'pricing_quote'))
    assert route['owner']=='Support L1'
    assert not route['should_escalate']


def test_declined_relationship_keeps_its_existing_provisional_route():
    history=[{'role':'user','text':'Quote a routing deployment for 250,000 calls.'},
             {'role':'assistant','text':'Are you a new or existing customer?'}]
    query="Let's leave that open for now."
    route=route_enquiry(query,parsed_for(query,'pricing_quote'),history=history)
    assert route['owner']=='Support L1'
    assert route['ownership_review']['status_deferred']
    assert route['ownership_review']['suggested_question'] is None
