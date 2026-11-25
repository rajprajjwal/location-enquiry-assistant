"""Hand-calculated metrics and artifact binding regressions."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from copilot.evaluation.retrieval import score
from copilot.evaluation.artifacts import aggregate,publish,rescore
from copilot.evaluation.contracts import METRICS
from copilot.evaluation.data import read_cases,sample,digest
from copilot.evaluation.holdout import reserve


def test_rank_metrics_keep_missing_gold_and_ignore_duplicate_labels():
    citations=[{'url':'https://example.test/a','span':'exact required fact','quote_or_summary':'verbatim'},
               {'url':'https://example.test/b','span':'another fact','quote_or_summary':'verbatim'},
               {'url':'https://example.test/a','span':'exact required fact','quote_or_summary':'verbatim'}]
    hits=[{'doc_url':'https://example.test/unrelated','text':'nothing'},
          {'doc_url':'https://example.test/a','text':'The exact required fact is here.'}]
    result=score(hits,citations)
    assert result['span_recall_at_1']==0
    assert result['span_recall_at_5']==result['span_recall_at_10']==.5
    assert result['span_mrr']==.5 and result['source_recall_at_5']==.5
    assert result['verbatim_labels']==2


def test_same_text_on_wrong_url_and_summary_do_not_count_as_exact_span():
    result=score([{'doc_url':'https://example.test/b','text':'exact fact'}],
                 [{'url':'https://example.test/a','span':'exact fact','quote_or_summary':'verbatim'},
                  {'url':'https://example.test/b','span':'summary','quote_or_summary':'summary'}])
    assert result['span_recall_at_10']==0 and result['summary_labels']==1


def test_aggregation_retains_all_metrics_and_na_denominators(tmp_path):
    records=[{'record_id':'SYN-1','arm':arm,'bucket':'docs','api':'directions','team':'Support',
              'metrics':{k:(.75 if k=='answer_accuracy' else None) for k in METRICS}} for arm in ('baseline','agent')]
    summary=publish(tmp_path,{'split':'synthetic','binding':{'strategy':'zero_shot','retrieval':'fixture'}},records)
    (tmp_path/'records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    assert rescore(tmp_path)['metric_delta']==0
    assert {r['metric'] for r in summary['metrics']}==set(METRICS)
    na=next(r for r in summary['metrics'] if r['metric']=='history_use')
    assert na['score'] is None and na['scored']==0 and na['cases']==1
    records[0]['metrics']['answer_accuracy']=1
    (tmp_path/'records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    with pytest.raises(ValueError,match='differ'):
        rescore(tmp_path)


def test_grouped_sample_excludes_frozen_and_validation_groups():
    cases=read_cases()
    discovery=sample(cases)
    validation=sample(cases,exclude_groups=[c['group'] for c in discovery])
    assert len(discovery)==len(validation)==10
    assert not {c['group'] for c in discovery}&{c['group'] for c in validation}
    assert all(c['split']=='working_eval' for c in discovery+validation)


def test_holdout_requires_review_before_reserving_any_calls(tmp_path):
    approval=tmp_path/'review.json'
    approval.write_text(json.dumps({'approved':False}))
    selected=tmp_path/'selection.json'
    selected.write_text(json.dumps({'locked':True,'repeatability_passed':True}))
    with pytest.raises(ValueError,match='review'):
        reserve([],approval,selected,tmp_path/'ledger.json',tmp_path/'out')
    assert not (tmp_path/'ledger.json').exists()


def test_citation_index_requires_the_correct_document_and_real_quote(monkeypatch):
    from copilot.evaluation.scoring import citation_evidence,corpus_by_url
    from copilot.evaluation.contracts import Prediction
    from copilot.rag.document_indexing import bm25
    monkeypatch.setattr(bm25,'load_chunks',lambda:[{'doc_url':'https://example.test/docs','text':'The rate limit is 40 requests per second.'}])
    corpus_by_url.cache_clear()
    prediction=Prediction(answer='The limit is 40 requests per second.',
        citations=[{'url':'https://example.test/docs','span':'40 requests per second','supports_claim':'The limit.'},
                   {'url':'https://example.test/fake','span':'40 requests per second','supports_claim':'The limit.'}],
        clarifying_questions=[],qualification={},comparison={},owner=None,next_action=None,
        should_escalate=None,record_update=None,intent=None,api=None,team=None)
    evidence,binding=citation_evidence(prediction)
    assert binding==[True,False] and len(evidence)==1
    corpus_by_url.cache_clear()


def test_empty_citations_never_inherit_flags_for_reference_citations():
    from types import SimpleNamespace
    from copilot.evaluation.judge import evaluate
    from copilot.evaluation.contracts import Prediction
    p=Prediction(answer='An answer.',citations=[],clarifying_questions=[],qualification={},comparison={},
                 owner=None,next_action=None,should_escalate=None,record_update=None,intent=None,api=None,team=None)
    response={'answer_accuracy':0,'grounding':0,'comparison_completeness':0,'qualification_completeness':0,
              'history_use':0,'citation_supported':[True],'reasons':{}}
    client=SimpleNamespace(complete=lambda *a,**kw:SimpleNamespace(text=json.dumps(response),finish_reason='stop'))
    case={'input':{},'rubric':'One criterion.','gold':{'outputs':{'response_draft':{'draft_text':'Reference.'},'qualification_details':{},'comparison':{}}}}
    assert evaluate(case,p,[],client).citation_supported==[]


def test_final_holdout_allows_only_exact_resume_of_the_same_run(tmp_path,monkeypatch):
    from copilot.evaluation import holdout
    monkeypatch.setattr(holdout,'split_pairs',lambda:[])
    monkeypatch.setattr(holdout,'file_hash',lambda path: str(path) if str(path).endswith('selection.json') else 'fixed')
    approval=tmp_path/'review.json'
    approval.write_text(json.dumps({'approved':True,'reviewer':'Synthetic test reviewer',
        'workbook_sha256':'fixed','leakage_audit_sha256':'fixed','case_ids':['SYN-1'],'duplicate_dispositions':[]}))
    selected=tmp_path/'selection.json'
    selected.write_text(json.dumps({'locked':True,'repeatability_passed':True,'fresh_judge_repeatability_passed':True}))
    cases=[{'record_id':'SYN-1'}]
    ledger=tmp_path/'ledger.json'
    assert holdout.reserve(cases,approval,selected,ledger,tmp_path/'first')==cases
    assert holdout.reserve(cases,approval,selected,ledger,tmp_path/'first')==cases
    with pytest.raises(ValueError,match='another run'):
        holdout.reserve(cases,approval,selected,ledger,tmp_path/'second')


def test_citation_precision_cannot_credit_an_unbound_source():
    from copilot.evaluation.scoring import metrics
    from copilot.evaluation.contracts import Judgement
    case={'input':{'history':[]},'gold':{'tools_expected':[],
        'outputs':{'qualification_details':{},'comparison':{'applicable':False},'responsible_role':{'owner':'Support L1'},
                   'next_action':{'action_type':'answer_directly'}}}}
    row={'arm':'baseline','prediction':{'qualification':{},'owner':'Support L1','next_action':'answer_directly'},
         'has_draft':True,'usage':{}}
    judged=Judgement(answer_accuracy=1,grounding=1,comparison_completeness=1,
                     qualification_completeness=1,history_use=1,citation_supported=[True],reasons={})
    result=metrics(case,row,judged,[False])
    assert result['citation_precision']==result['citation_coverage']==0
    assert result['history_use'] is None and result['comparison_completeness'] is None


def test_strict_qualification_counts_fields_and_normalizes_volume_raw_text():
    from copilot.evaluation.scoring import qualification_checks
    expected={'region':'India','current_provider':None,'monthly_volume':{'raw':'2M requests','requests_per_month':2000000,'unit':'requests_per_month'},
              'missing_required_fields':['timeline','budget'],'complete':False}
    actual={'region':' india ','current_provider':None,'monthly_volume':{'raw':'2,000,000 per month','requests_per_month':2000000,'unit':'requests_per_month'},
            'missing_required_fields':['budget','timeline']}
    checks=qualification_checks(actual,expected)
    assert len(checks)==4 and all(checks.values())
    del actual['current_provider']
    assert sum(qualification_checks(actual,expected).values())==3
    actual['monthly_volume']['requests_per_month']=2000
    assert sum(qualification_checks(actual,expected).values())==2


def test_verified_pricing_excerpt_can_support_a_citation_outside_chunk_text(monkeypatch):
    from copilot.evaluation.scoring import citation_evidence,corpus_by_url
    from copilot.evaluation.contracts import Prediction
    from copilot.rag.document_indexing import bm25
    from copilot.paths import REPO_ROOT
    source=json.loads((REPO_ROOT/'copilot/config/pricing-evidence.json').read_text())['offers']['ola.autocomplete']
    monkeypatch.setattr(bm25,'load_chunks',lambda:[])
    corpus_by_url.cache_clear()
    prediction=Prediction(answer='The documented rate is given in the source.',
        citations=[{'url':source['url'],'span':source['span'],'supports_claim':'The documented rate.'}],
        clarifying_questions=[],qualification={},comparison={},owner=None,next_action=None,
        should_escalate=None,record_update=None,intent=None,api=None,team=None)
    evidence,bound=citation_evidence(prediction)
    assert bound==[True] and evidence[0]['text']
    corpus_by_url.cache_clear()


def test_prompt_examples_use_the_existing_complete_qualification_contract():
    from copilot.evaluation.baselines import EXAMPLES
    from copilot.response_drafting.schemas import _validator
    for _,prediction in EXAMPLES:
        assert not list(_validator('qualification_details').iter_errors(prediction['qualification']))
        assert set(prediction['qualification'])==set(_validator('qualification_details').schema['properties'])
        assert not list(_validator('comparison').iter_errors(prediction['comparison']))
