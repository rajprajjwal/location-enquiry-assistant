"""Validate final staff questions and keep checklist advice on the same plan."""
from hashlib import sha256
import json

from pydantic import ValidationError
from copilot.observability.tracing import phase

from copilot.enquiry_workflow.routing import asks_qualification
from copilot.response_drafting.schemas import validate_outputs
from .decisions import RequirementPlan
from .task import effective_customer_task


@phase("output_validation")
def finalize_requirements(result, enquiry):
    """Keep route and pending controls intact; validate the final assembled output."""
    if 'requirement_plan' not in result:
        return result
    try:
        plan = RequirementPlan.model_validate(result['requirement_plan'])
    except ValidationError:
        return {**result, 'final_validation': {'valid': False, 'errors': ['Invalid requirement-plan schema.']}}
    outputs = result['outputs']
    questions = outputs['clarifying_questions']['questions']
    errors = []
    if plan.task != effective_customer_task(enquiry):
        errors.append('Requirement plan belongs to another customer task.')
    texts = [question['text'] for question in questions]
    if any(decision.question not in texts for decision in plan.decisions):
        errors.append('A selected requirement is absent from the structured question list.')
    fields = [field for decision in plan.decisions for field in decision.fields]
    if len(fields) != len(set(fields)):
        errors.append('The requirement plan repeats a selected fact.')

    draft = result.get('response_draft')
    if not errors and draft and result['status'] == 'final' and asks_qualification(plan.task):
        advice = 'Qualification follow-ups:\n' + ('\n'.join('- ' + decision.question for decision in plan.decisions)
                  if plan.decisions else 'The selected requirements have already been supplied, assumed, asked or declined.')
        text = draft['draft_text']
        # Replace only the generated advice section; retain all documented provider claims and citations.
        if text.startswith('Before recommending a provider, confirm the remaining customer requirements:'):
            marker = 'Retrieved documentation excerpts (reference only):'
            evidence = text[text.index(marker):] if marker in text else ''
            text = '\n\n'.join(part for part in (advice, evidence) if part)
        elif text.startswith('Before recommending a provider, confirm the number of origins and destinations per batch,'):
            text = advice + '\n\n' + text.split('\n\n', 1)[1] if '\n\n' in text else advice
        elif '\n\nQualification follow-ups:\n' in text:
            text = text.split('\n\nQualification follow-ups:\n', 1)[0] + '\n\n' + advice
        elif not text.startswith('Qualification follow-ups:'):
            text += '\n\n' + advice
        else:
            _, separator, references = text.partition('\n\n')
            text = advice + (separator + references if separator else '')
        draft = {**draft, 'draft_text': text}
        outputs = {**outputs, 'response_draft': draft}
    errors.extend(validate_outputs(outputs))
    return {**result, 'outputs': outputs, 'response_draft': draft,
            'final_validation': {'valid': not errors, 'errors': errors,
                'plan_sha256': sha256(json.dumps(plan.model_dump(mode='json'), sort_keys=True).encode()).hexdigest(),
                'selected_decisions': len(plan.decisions), 'selected_facts': len(fields)}}
