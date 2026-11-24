"""Answer a requested qualification checklist without opening an intake question."""
from urllib.parse import urlsplit

from copilot.diagnostics.facts import build_diagnostic_state

from .facts import context_from_result
from .requirements import applicable_groups
from .decisions import requirement_plan
from .task import effective_customer_task


def checklist_draft(enquiry, interpretation, passages, pricing=None, *, plan=None, state=None):
    """Render missing customer decisions and quote available references separately."""
    payload = interpretation.model_dump(mode='json')
    if not payload.get('api') or not payload.get('intent'):
        return None
    result = {
        'diagnostic_context': {'interpretation': {'api': payload['api'], 'intent': payload['intent']}},
        'outputs': {'qualification_details': payload['qualification_details']},
    }
    state = state or build_diagnostic_state(enquiry)
    context = context_from_result(result, state, enquiry)
    groups = applicable_groups(context, enquiry, pricing or {})
    if not groups:
        return None

    plan = plan or requirement_plan(context, state, groups, effective_customer_task(enquiry), checklist=True)
    questions = [decision.question for decision in plan.decisions]

    if questions:
        sections = ['Before recommending a provider, confirm the remaining customer requirements:',
                    '\n'.join('- ' + question for question in questions)]
    else:
        sections = ['The customer has supplied the requirements in this checklist. '
                    'Verify product fit against current provider documentation.']

    citations = []
    seen = set()
    for passage in passages or []:
        url, span = passage.get('source_url'), passage.get('relevant_passage')
        if not isinstance(url, str) or not isinstance(span, str) or not span.strip():
            continue
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            continue
        span = span.strip()
        if (url, span) in seen:
            continue
        seen.add((url, span))
        citations.append({'url': url, 'span': span, 'supports_claim': span,
                          'quote_or_summary': 'verbatim'})
        if len(citations) == 3:
            break
    if citations:
        # Checklist advice is separate from the provider statements quoted as evidence.
        sections.append('Retrieved documentation excerpts (reference only):')
        sections.extend(f'[{index}] {citation["span"]}'
                        for index, citation in enumerate(citations, 1))
    else:
        sections.append('This checklist is qualification advice. No provider-specific claims have been verified.')
    from copilot.enquiry_workflow.answers import make_draft

    return make_draft('\n\n'.join(sections), citations)
