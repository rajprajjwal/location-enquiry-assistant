"""The classifier receives the customer request without staff routing instructions."""
from copilot.enquiry_interpretation.interpret import build_messages
from copilot.enquiry_interpretation.rules import extract


def test_staff_wrapper_is_not_sent_as_the_customer_classification_request(monkeypatch):
    from copilot.enquiry_interpretation import fewshot
    monkeypatch.setattr(fewshot, 'load_examples', lambda: [])
    body = 'Our Directions request returns an authorization error.'
    query = f'Sandbox CRM ticket TKT-12345. Customer wrote: "{body}" Who should own this, and should it be escalated?'
    messages = build_messages({'query': query, 'history': [], 'known_facts': []}, extract([], query))
    message = messages[-1]['content'].split('MESSAGE:', 1)[1].strip()
    assert message == body
    assert 'Who should own this' not in messages[-1]['content']
