"""The confirmed task policy applies even without a stated buying decision."""
import pytest

from copilot.enquiry_workflow.escalation import route_enquiry
from tests.enquiry_workflow.test_escalation import parsed_for


@pytest.mark.parametrize(('query','intent'),[
    ('Which mapping APIs support bicycle routes?','capability_match'),
    ('Which reverse geocoders support house numbers?','docs_how_to'),
    ('Which of Google and Mapbox document place-type filters?','capability_match'),
    ('Can a directions API provide audio guidance for our drivers?','capability_match'),
])
def test_unconfirmed_provider_feature_discovery_is_provisional_sales(query,intent):
    route=route_enquiry(query,parsed_for(query,intent))
    assert route['owner']=='Account team (Sales)'
    assert route['ownership_review']['customer_status']=='unknown'
    assert route['ownership_review']['provisional']
    assert not route['should_escalate']


@pytest.mark.parametrize('query',[
    "What's the Google Geocoding API request limit?",
    'What rate can we call the public Nominatim API at?',
    'What attribution is required for the Nominatim Reverse API?',
    'Which API parameter controls the language in Google Directions?',
])
def test_a_parameter_or_policy_question_does_not_become_provider_discovery(query):
    route=route_enquiry(query,parsed_for(query,'docs_how_to'))
    assert route['owner']=='Support L1'


def test_confirmed_existing_customer_still_receives_support():
    query='Which mapping APIs support bicycle routes?'
    route=route_enquiry(query,parsed_for(query,'capability_match'),confirmed_customer_status='existing')
    assert route['owner']=='Support L1'
    assert not route['ownership_review']['provisional']


@pytest.mark.parametrize('query',[
    'We need a 25 by 25 matrix with 625 elements per request. Which providers accept it in one call?',
    'Our routing batch has 36 stops. Which providers accept it in a single request?',
    'Which providers can calculate a 600×600 matrix using the fewest calls?',
])
def test_numeric_request_feasibility_keeps_documentation_support(query):
    route=route_enquiry(query,parsed_for(query,'docs_how_to'))
    assert route['owner']=='Support L1'
    assert route['ownership_review']['customer_status']=='unknown'
