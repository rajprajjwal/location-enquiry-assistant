"""Run the existing agent in an isolated database and normalize its outputs."""
from copilot.case_storage import cases
from copilot.enquiry_workflow.cases import run_case
from .contracts import Prediction


def run_agent(con,context,client,search):
    identifier=cases.create_case(con,customer='evaluation sandbox')
    for turn in context['history']:
        cases.add_message(con,identifier,turn['role'],turn['text'])
    if context['known_facts']:
        raise ValueError('Use approved inputs with empty initial known facts')
    result=run_case(con,context['query'],case_id=identifier,client=client,search=search)
    outputs=result['outputs']
    draft=result.get('response_draft') or {}
    state=cases.load_state(con,identifier)
    interpretation=state['interpretation']
    prediction=Prediction(answer=draft.get('draft_text',''),
        citations=[{k:c[k] for k in ('url','span','supports_claim')} for c in draft.get('citations',[])],
        clarifying_questions=[q['text'] for q in outputs['clarifying_questions']['questions']],
        qualification=outputs['qualification_details'],comparison=outputs['comparison'],
        owner=outputs['responsible_role']['owner'],next_action=outputs['next_action']['action_type'],
        should_escalate=outputs['responsible_role']['should_escalate'],
        record_update=outputs['proposed_record_update'],intent=interpretation['intent'],
        api=interpretation['api'],team=interpretation['team'])
    return prediction,result
