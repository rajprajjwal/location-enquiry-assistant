"""Score paired predictions with explicit applicability and citation evidence."""
from collections import defaultdict
from functools import lru_cache
import json
from hashlib import sha256
from copilot.paths import REPO_ROOT
from .retrieval import canonical, normalize
from .contracts import METRICS


@lru_cache(maxsize=1)
def corpus_by_url():
    from copilot.rag.document_indexing.bm25 import load_chunks
    result = defaultdict(list)
    for chunk in load_chunks():
        result[canonical(chunk['doc_url'])].append(chunk)
    pricing=REPO_ROOT/'copilot/config/pricing-evidence.json'
    snapshots=json.loads(pricing.read_text())
    corpus=REPO_ROOT/'copilot/rag/data/processed/chunks.jsonl'
    if snapshots['provenance']['indexed_pricing_sha256']!=sha256(corpus.read_bytes()).hexdigest():
        raise ValueError('Pricing evidence belongs to a different indexed corpus')
    def add(value):
        if isinstance(value,dict):
            if value.get('url') and value.get('span'):
                result[canonical(value['url'])].append({'doc_url':value['url'],'text':value['span']})
            for child in value.values():
                add(child)
        elif isinstance(value,list):
            for child in value:
                add(child)
    add(snapshots)
    return result


def qualification_checks(actual,expected):
    """Strict, reproducible field agreement; no inferred paraphrase credit."""
    def equal(a,b):
        if isinstance(b,str):
            return isinstance(a,str) and normalize(a)==normalize(b)
        if isinstance(b,list):
            return isinstance(a,list) and sorted(a)==sorted(b)
        if isinstance(b,dict):
            return isinstance(a,dict) and all(k in a and equal(a[k],v) for k,v in b.items() if k!='raw')
        return type(a) is type(b) and a==b
    return {field:field in actual and equal(actual[field],value) for field,value in expected.items()
            if field!='complete'}


def citation_evidence(prediction, retrieved=()):
    evidence, bound = [], []
    for index,citation in enumerate(prediction.citations):
        matches = [c for c in corpus_by_url().get(canonical(citation.url),())
                   if normalize(citation.span) and normalize(citation.span) in normalize(c['text'])]
        matches += [h for h in retrieved if canonical(h.get('source_url',h.get('doc_url','')))==canonical(citation.url)
                    and normalize(citation.span) and normalize(citation.span) in normalize(h.get('relevant_passage',h.get('text','')))]
        bound.append(bool(matches))
        if matches:
            evidence.append({'citation_index':index,'url':citation.url,'text':citation.span[:1800]})
    for hit in retrieved[:8]:
        evidence.append({'url':hit.get('source_url',hit.get('doc_url','')),
                         'text':hit.get('relevant_passage',hit.get('text',''))[:900]})
    return evidence,bound


def metrics(case,record,judgement=None,bound=()):
    prediction = record.get('prediction')
    expected = case['gold']['outputs']
    comparison = expected['comparison']['applicable']
    history = bool(case['input']['history'])
    if not prediction:
        result = {k:None for k in METRICS}
        result.update(answer_accuracy=0,grounding=0,qualification_completeness=0,owner_accuracy=0,
                      next_action_correctness=0,schema_validity=0,draft_yield=0,
                      comparison_completeness=0 if comparison else None,history_use=0 if history else None)
    else:
        supported = [valid and yes for valid,yes in zip(bound,judgement.citation_supported)] if judgement else []
        has_draft = record['has_draft']
        result = {k:None for k in METRICS}
        result.update(schema_validity=1,draft_yield=int(has_draft),
                      owner_accuracy=int(prediction['owner']==expected['responsible_role']['owner']),
                      next_action_correctness=int(prediction['next_action']==expected['next_action']['action_type']),
                      citation_coverage=int(any(supported)) if has_draft and judgement else None,
                      citation_precision=sum(supported)/len(bound) if bound and judgement else None)
        if judgement:
            result.update({k:getattr(judgement,k) for k in ('answer_accuracy','grounding')})
            result.update(comparison_completeness=judgement.comparison_completeness if comparison else None,
                          history_use=judgement.history_use if history else None)
    if prediction:
        checks=qualification_checks(prediction['qualification'],expected['qualification_details'])
        result['qualification_completeness']=sum(checks.values())/len(checks) if checks else None
    if record['arm']=='agent':
        calls = record.get('tool_calls',[])
        result['tool_execution_success'] = (sum(c.get('registered') and c.get('execution_status')=='success'
            and c.get('input_validation')=='passed' and c.get('output_validation')=='passed' for c in calls)/len(calls)) if calls else None
        aliases = {'doc_search':'document_search','calculator':'compare_providers','update_record':'sandbox_record_update',
                   'escalate_ticket':'propose_escalation'}
        expected_tools = set(case['gold']['tools_expected'])-{'escalate_ticket'}
        succeeded = {c['tool_name'] for c in calls if c.get('execution_status')=='success'}
        result['expected_tool_coverage'] = (sum(aliases.get(t,t) in succeeded for t in expected_tools)/len(expected_tools)
                                           if expected_tools else None)
        result.update({k:v for k,v in record.get('retrieval_metrics',{}).items() if k in METRICS})
    usage = record.get('usage',{})
    result.update(latency_ms=record.get('latency_ms'),cost_inr=float(usage['cost_inr']) if usage.get('cost_inr') is not None else None,
                  **{k:usage.get(k) if usage.get('usage_complete') else None for k in ('input_tokens','output_tokens','embedding_tokens')})
    result['judge_latency_ms']=record.get('judge_latency_ms')
    result['retrieval_probe_latency_ms']=record.get('retrieval_latency_ms')
    for name,key in [('judge_cost_inr','judge_usage'),('retrieval_probe_cost_inr','retrieval_usage')]:
        value=record.get(key,{}).get('cost_inr')
        result[name]=float(value) if value is not None else None
    return result
