"""One resumable command generates both arms, scores them and publishes metrics."""
import argparse
from contextlib import closing
from datetime import datetime,timezone
import json
import os
from pathlib import Path
from time import perf_counter

from copilot.case_storage.db import connect
from copilot.enquiry_workflow.retrieval import rag_document_search,warm_retrieval_runtime,retrieval_setup_issues
from copilot.model_gateway.client import LLMClient
from copilot.model_gateway.reliability import query_session
from copilot.observability import trace_run
from copilot.observability.tracing import provider
from copilot.paths import REPO_ROOT
from . import artifacts,baselines,judge
from .adapters import run_agent
from .contracts import Prediction
from .data import read_cases,sample,file_hash,digest,WORKBOOK
from .retrieval import probe,score as score_retrieval
from .scoring import citation_evidence,metrics,qualification_checks


def implementation_hash():
    paths = sorted(p for p in (REPO_ROOT/'copilot').rglob('*.py')
                   if not {'results','runtime','__pycache__'} & set(p.parts))
    paths += sorted((REPO_ROOT/'copilot/config').glob('*.*'))
    paths += sorted((REPO_ROOT/'schemas').glob('*.json'))
    return digest({str(p.relative_to(REPO_ROOT)):file_hash(p) for p in paths})


def append(path,row):
    with path.open('a') as stream:
        stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
        stream.flush()
        os.fsync(stream.fileno())


def read_rows(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l] if path.exists() else []


def _run(folder,cases,*,strategy='zero_shot',mode='hybrid',arms=('baseline','agent'),client=None):
    client=client or LLMClient()
    if mode=='hybrid':
        issues=retrieval_setup_issues(mode,rerank=True)
        if issues:
            raise ValueError('; '.join(issues))
        warm_retrieval_runtime()
    binding={'workbook_sha256':file_hash(WORKBOOK),'cases_sha256':digest(cases),
             'implementation_sha256':implementation_hash(),'corpus_sha256':file_hash(REPO_ROOT/'copilot/rag/data/processed/chunks.jsonl'),
             'rates_sha256':file_hash(REPO_ROOT/'copilot/config/observability.yaml'),
             'strategy':strategy,'retrieval':mode,'arms':list(arms),'case_ids':[c['record_id'] for c in cases]}
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/'manifest.json'
    if path.exists():
        manifest=json.loads(path.read_text())
        if manifest['binding']!=binding:
            raise ValueError('Resume inputs or implementation changed; use a new run directory')
    else:
        manifest={'binding':binding,'started_at':datetime.now(timezone.utc).isoformat(),
                  'split':cases[0]['split'],'holdout_cases':sum(c['split']=='holdout' for c in cases),
                  'gold_status':'Project GT; automatic judge scores require human interpretation.',
                  'judge_model':getattr(client,'_model','configured endpoint'),'judge_type':'same-endpoint automatic reference-based review',
                  'cost_basis':'illustrative reporting estimates; actual institute endpoints free',
                  'retrieval_scope':'Independent top-10 probe using query and user history; verbatim span and source URL diagnostics. Summary labels excluded from strict span denominator.'}
        path.write_text(json.dumps(manifest,indent=2)+'\n')
    snapshot=folder/'cases.jsonl'
    if not snapshot.exists():
        snapshot.write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in cases))
    elif digest(read_rows(snapshot))!=binding['cases_sha256']:
        raise ValueError('Saved gold snapshot changed')
    records=read_rows(folder/'records.jsonl')
    generations={(r['record_id'],r['arm']):r for r in read_rows(folder/'generations.jsonl')}
    completed={(r['record_id'],r['arm']) for r in records}
    if len(completed)!=len(records) or any(pair[0] not in binding['case_ids'] for pair in completed):
        raise ValueError('Duplicate or foreign records in resume journal')
    inflight=folder/'inflight.json'
    if inflight.exists():
        item=json.loads(inflight.read_text())
        if (item['record_id'],item['arm']) not in generations:
            raise ValueError('An interrupted generation has an ambiguous endpoint outcome; do not repeat holdout calls')
        inflight.unlink()
    search=rag_document_search(mode=mode,rerank=mode=='hybrid')
    with closing(connect(folder/'cases.db')) as con:
        for index,case in enumerate(cases,1):
            for arm in arms:
                key=(case['record_id'],arm)
                if key in completed:
                    continue
                metadata={k:case[k] for k in ('record_id','bucket','api','team','split')}
                if key not in generations:
                    inflight.write_text(json.dumps({'record_id':key[0],'arm':arm})+'\n')
                    record={**metadata,'arm':arm,'strategy':strategy if arm=='baseline' else 'agent',
                            'prediction':None,'tool_calls':[],'retrieved_evidence':[],'has_draft':False}
                    started=perf_counter()
                    capture=None
                    try:
                        with trace_run(connection=con,metadata={**metadata,'run_id':folder.name+'-'+arm}) as capture:
                            with query_session():
                                if arm=='baseline':
                                    prediction=baselines.run(case['input'],strategy,client)
                                    record['has_draft']=bool(prediction.answer.strip())
                                else:
                                    prediction,result=run_agent(con,case['input'],client,search)
                                    record.update(tool_calls=result['tool_calls'],retrieved_evidence=result.get('retrieved_evidence',[]),
                                                  status=result['status'],has_draft=bool(result['response_draft']))
                                record['prediction']=prediction.model_dump(mode='json')
                        record.update(trace_id=capture.trace_id,usage=capture.summary)
                    except Exception as error:
                        record['generation_error']=type(error).__name__
                        if capture is not None:
                            record.update(trace_id=capture.trace_id,usage=capture.summary)
                    record['latency_ms']=round((perf_counter()-started)*1000,3)
                    append(folder/'generations.jsonl',record)
                    generations[key]=record
                    inflight.unlink()
                record=dict(generations[key])
                judgement=None
                bound=[]
                if record['prediction'] is not None:
                    prediction=Prediction.model_validate(record['prediction'])
                    evidence,bound=citation_evidence(prediction,record['retrieved_evidence'])
                    started=perf_counter()
                    try:
                        with trace_run(metadata={**metadata,'run_id':folder.name+'-judge'}) as review:
                            judgement=judge.evaluate(case,prediction,evidence,client)
                        record.update(judgement=judgement.model_dump(),judge_usage=review.summary,judge_trace_id=review.trace_id)
                    except Exception as error:
                        record['judge_error']=type(error).__name__
                    record['judge_latency_ms']=round((perf_counter()-started)*1000,3)
                if arm=='agent':
                    started=perf_counter()
                    try:
                        with trace_run(metadata={**metadata,'run_id':folder.name+'-retrieval'}) as retrieval_run:
                            ranked=probe(case['input'],mode)
                        record.update(retrieval_metrics=score_retrieval(ranked,case['gold']['outputs']['response_draft']['citations']),
                                      retrieval_usage=retrieval_run.summary,retrieval_hits=ranked)
                    except Exception as error:
                        record['retrieval_error']=type(error).__name__
                    record['retrieval_latency_ms']=round((perf_counter()-started)*1000,3)
                if record.get('prediction'):
                    record['qualification_checks']=qualification_checks(record['prediction']['qualification'],case['gold']['outputs']['qualification_details'])
                record['citation_source_binding']=bound
                record['metrics']=metrics(case,record,judgement,bound)
                append(folder/'records.jsonl',record)
                records.append(record)
                completed.add(key)
                print(f'{index}/{len(cases)} {key[0]} {arm}: '+('error' if record.get('generation_error') or record.get('judge_error') else 'scored'),flush=True)
    provider().force_flush(timeout_millis=40000)
    summary=artifacts.publish(folder,manifest,records)
    repeat=artifacts.rescore(folder)
    (folder/'repeatability.json').write_text(json.dumps(repeat,indent=2)+'\n')
    return summary


def run(folder,cases,**options):
    from copilot.file_lock import try_lock
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    with (folder/'.run.lock').open('a') as lock:
        try:
            try_lock(lock)
        except BlockingIOError as error:
            raise ValueError('This evaluation output is already in use') from error
        return _run(folder,cases,**options)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--split',choices=['working_eval','frozen','holdout'],default='working_eval')
    parser.add_argument('--strategy',choices=baselines.STRATEGIES,default='zero_shot')
    parser.add_argument('--mode',choices=['bm25','hybrid'],default='hybrid')
    parser.add_argument('--sample-per-bucket',type=int)
    parser.add_argument('--selection',type=Path)
    parser.add_argument('--exclude-selection-groups',action='store_true')
    parser.add_argument('--holdout-approval',type=Path)
    parser.add_argument('--final-holdout',action='store_true')
    args=parser.parse_args(argv)
    if args.split=='holdout' and not(args.final_holdout and args.selection and args.holdout_approval):
        parser.error('Holdout requires --final-holdout, --selection and --holdout-approval')
    if args.split!='working_eval' and args.sample_per_bucket:
        parser.error('Sampling is restricted to working-eval')
    cases=read_cases(args.split)
    strategy=args.strategy
    if args.selection:
        selection=json.loads(args.selection.read_text())
        if selection.get('implementation_sha256')!=implementation_hash():
            parser.error('The locked selection does not match the current implementation')
        for key,path in [('workbook_sha256',WORKBOOK),('corpus_sha256',REPO_ROOT/'copilot/rag/data/processed/chunks.jsonl')]:
            if selection.get(key)!=file_hash(path):
                parser.error('The selection data or corpus binding changed')
        if args.split!='working_eval' and not selection.get('locked'):
            parser.error('Lock a verified selection before frozen or holdout evaluation')
        strategy=selection['strategy']
    if args.split=='holdout':
        from .holdout import reserve
        cases=reserve(cases,args.holdout_approval,args.selection,REPO_ROOT/'results/evaluation/holdout-ledger.json',args.out)
    if args.exclude_selection_groups and (args.split!='working_eval' or not args.selection):
        parser.error('Excluding selection groups requires a working-eval selection file')
    excluded=selection.get('excluded_validation_groups',[]) if args.exclude_selection_groups else []
    if args.sample_per_bucket:
        cases=sample(cases,args.sample_per_bucket,exclude_groups=excluded)
    elif excluded:
        cases=[c for c in cases if c['group'] not in set(excluded)]
    summary=run(args.out,cases,strategy=strategy,mode=args.mode)
    print(json.dumps({'paired_cases':summary['paired_cases'],'errors':summary['errors'],'metrics_sha256':summary['metrics_sha256']}))


if __name__=='__main__':
    main()
