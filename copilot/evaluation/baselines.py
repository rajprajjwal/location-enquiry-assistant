# Source history: Raj Kumar (a3ef3a6), prompting strategies adapted from
# prompt-engineering-baseline/app/baseline/prompting.py. Demo labels and scoring are not reused.
"""Canonical plain-model strategies without retrieval or action execution."""
from collections import Counter
import json
from copilot.model_gateway.client import LLMClient
from .contracts import Prediction

STRATEGIES = ('zero_shot', 'few_shot', 'self_consistency', 'decomposition')
SYSTEM = '''You help sales and support staff with Directions, Distance Matrix, Autocomplete and Reverse Geocode enquiries.
Use the supplied query and chronological conversation history. Do not invent prices, coverage or source quotations.
Answer the staff member's actual task, carry forward known facts, ask only decision-relevant unanswered questions.
Record writes and handoffs are proposals pending human approval. Do not claim execution.
Return ONLY a compact JSON object with exactly these fields:
answer:string (at most 120 words); citations:[{url:string,span:string,supports_claim:string}];
clarifying_questions:[string]; qualification:object; comparison:object;
owner:"Support L1"|"Support L2"|"Account team (Sales)"|"Maps engineering"|null;
next_action:"answer_directly"|"ask_clarifying_questions"|"propose_record_update"|"propose_escalation"|"refuse"|null;
should_escalate:boolean|null; record_update:object|null; intent:string|null;
api:"directions"|"distance_matrix"|"autocomplete"|"reverse_geocode"|null; team:"Sales"|"Support"|null.
qualification MUST contain every field: use_case_api:{api:string|null,use_case:string|null}|null,
region:string|null,monthly_volume:{raw:string,requests_per_month:integer,unit:string}|null,
current_provider:string|null,timeline:string|null,budget:string|null,technical_constraints:string|null,decision_maker:string|null,
missing_required_fields:[string],complete:boolean. Use explicit nulls, never omit fields.
Required qualification facts are use_case_api,region,monthly_volume,current_provider,timeline; list absent facts in missing_required_fields.
complete is true only when those five facts are supplied. Do not invent facts to fill a field.
comparison MUST contain applicable:boolean,providers:[string],dimensions:[string],assumptions:[string],source_urls:[string]. Use applicable:false and empty lists when no comparison is requested.
Use null for unprovided facts. Citations must contain a real supporting quotation, not just a plausible URL.'''

# Synthetic examples avoid gold-case selection and frozen/holdout contamination.
EXAMPLES = [
    ({'query':'We use Mapbox Directions. Which request details should support collect for an HTTP 401?',
      'history':[], 'known_facts':[]},
     {'answer':'Collect a redacted failing request and the response body; do not send the token.',
      'citations':[], 'clarifying_questions':['Can you share a redacted failing request and response body?'],
      'qualification':{'current_provider':'Mapbox'}, 'comparison':{}, 'owner':'Support L1',
      'next_action':'ask_clarifying_questions','should_escalate':False,'record_update':None,
      'intent':'troubleshooting','api':'directions','team':'Support'}),
    ({'query':'What should we ask before comparing reverse-geocoding providers?',
      'history':[], 'known_facts':[]},
     {'answer':'Confirm operating regions, expected monthly volume, peak load and storage needs before comparing documented options.',
      'citations':[], 'clarifying_questions':['Which regions, monthly lookup volume, peak rate and storage requirements do you need?'],
      'qualification':{},'comparison':{'applicable':True,'dimensions':['pricing','coverage','limits']},
      'owner':'Account team (Sales)','next_action':'answer_directly','should_escalate':False,'record_update':None,
      'intent':'sales_qualification','api':'reverse_geocode','team':'Sales'}),
]


for query,example in EXAMPLES:
    api=example['api']
    provider=example['qualification'].get('current_provider')
    example['qualification']={
        'use_case_api':{'api':api,'use_case':None},'region':None,'monthly_volume':None,
        'current_provider':provider,'timeline':None,'budget':None,'technical_constraints':None,
        'decision_maker':None,'missing_required_fields':['region','monthly_volume',*(['current_provider'] if provider is None else []),'timeline'],
        'complete':False}
    example['comparison']={'applicable':False,'providers':[],'dimensions':[],'assumptions':[],'source_urls':[]}


def decode(completion):
    if completion.finish_reason == 'length':
        raise ValueError('Truncated baseline output')
    return Prediction.model_validate_json(completion.text)


def run(context, strategy, client=None):
    if strategy not in STRATEGIES:
        raise ValueError('Unknown prompting strategy')
    client = client or LLMClient()
    messages = [{'role':'system','content':SYSTEM}]
    if strategy == 'few_shot':
        for query, answer in EXAMPLES:
            messages += [{'role':'user','content':json.dumps(query)},
                         {'role':'assistant','content':json.dumps(answer)}]
    messages += [{'role':'user','content':json.dumps(context,ensure_ascii=False)}]
    if strategy == 'decomposition':
        parts = []
        for task in ('Identify intent and API.', 'Extract supplied facts.', 'Identify missing decision-critical facts.',
                     'Assess support diagnosis or sales qualification.', 'Recommend owner and next action.'):
            reply = client.complete([{'role':'system','content':task+' Reply concisely without hidden reasoning.'}, messages[-1]],
                                    max_tokens=160, temperature=0)
            parts.append({'task':task,'result':reply.text})
        messages.append({'role':'user','content':'Synthesize the following sub-results into the required JSON. '+json.dumps(parts)})
    options = [decode(client.complete(messages,max_tokens=1024,temperature=.6 if strategy=='self_consistency' else 0,
                                     response_format={'type':'json_object'}))
               for _ in range(3 if strategy=='self_consistency' else 1)]
    votes = Counter((r.intent,r.api,r.owner) for r in options)
    winner = max(votes,key=votes.get)
    return next(r for r in options if (r.intent,r.api,r.owner)==winner)
