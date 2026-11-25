"""Recover only the approved failed judgement without regenerating an answer."""
from pathlib import Path
from time import perf_counter
import json
import os
import runpy
import traceback

from copilot.evaluation import artifacts, judge
from copilot.evaluation.contracts import Prediction
from copilot.evaluation.data import digest, file_hash, WORKBOOK
from copilot.evaluation.runner import implementation_hash, read_rows
from copilot.evaluation.scoring import citation_evidence, metrics
from copilot.model_gateway.client import LLMClient
from copilot.observability import trace_run
from copilot.observability.tracing import provider


def main():
    root=Path('results/evaluation')
    folder=root/'holdout-final'
    audit=root/'verification/judge-recovery-AC-050'
    if audit.exists():
        raise ValueError('Recovery already attempted; inspect its saved audit before proceeding')
    locked=json.loads((root/'locked-selection.json').read_text())
    manifest=json.loads((folder/'manifest.json').read_text())
    assert implementation_hash()==locked['implementation_sha256']==manifest['binding']['implementation_sha256']
    assert file_hash(WORKBOOK)==locked['workbook_sha256']==manifest['binding']['workbook_sha256']
    assert file_hash(Path('copilot/rag/data/processed/chunks.jsonl'))==manifest['binding']['corpus_sha256']
    assert file_hash(Path('copilot/config/observability.yaml'))==manifest['binding']['rates_sha256']
    resources=json.loads((root/'resource-binding.json').read_text())['tracked_resources_sha256']
    assert all(file_hash(Path(p))==h for p,h in resources.items())
    cases=read_rows(folder/'cases.jsonl')
    assert digest(cases)==manifest['binding']['cases_sha256']
    lines=(folder/'records.jsonl').read_bytes().splitlines(keepends=True)
    rows=[json.loads(line) for line in lines]
    indexes=[i for i,r in enumerate(rows) if (r['record_id'],r['arm'])==('GT-LBS-AC-050','baseline')]
    assert len(indexes)==1
    index=indexes[0]
    original=rows[index]
    assert original.get('judge_error')=='ValueError' and not original.get('generation_error')
    generation_hash=file_hash(folder/'generations.jsonl')
    record_hash=file_hash(folder/'records.jsonl')
    case=next(c for c in cases if c['record_id']==original['record_id'])
    audit.mkdir()
    (audit/'original-record.json').write_text(json.dumps(original,indent=2)+'\n')
    (audit/'original-summary.json').write_bytes((folder/'summary.json').read_bytes())
    client=LLMClient()
    calls=[]

    class RecordingClient:
        def complete(self,messages,**kwargs):
            response=client.complete(messages,**kwargs)
            calls.append({'request_sha256':digest({'messages':messages,**kwargs}),
                          'parameters':kwargs,'finish_reason':response.finish_reason,
                          'response_text':response.text})
            return response

    prediction=Prediction.model_validate(original['prediction'])
    evidence,bound=citation_evidence(prediction,original.get('retrieved_evidence',[]))
    assert bound==original['citation_source_binding']
    started=perf_counter()
    capture=None
    try:
        with trace_run(metadata={'record_id':original['record_id'],'bucket':original['bucket'],
                                 'api':original['api'],'team':original['team'],'split':'holdout',
                                 'run_id':'holdout-final-single-judge-recovery'}) as capture:
            result=judge.evaluate(case,prediction,evidence,RecordingClient())
    except Exception as error:
        (audit/'retry-failure.json').write_text(json.dumps({'type':type(error).__name__,
            'message':str(error),'traceback':traceback.format_exc(),'calls':calls},indent=2)+'\n')
        raise
    elapsed=round((perf_counter()-started)*1000,3)
    updated=dict(original)
    updated.pop('judge_error')
    updated.update(judgement=result.model_dump(),judge_usage=capture.summary,
                   judge_trace_id=capture.trace_id,judge_latency_ms=elapsed)
    updated['metrics']=metrics(case,updated,result,bound)
    updated['judge_recovery']={'original_error':'ValueError','original_attempt_latency_ms':original['judge_latency_ms'],
                               'audit_directory':str(audit),'generation_repeated':False}
    assert updated['prediction']==original['prediction']
    assert file_hash(folder/'records.jsonl')==record_hash
    lines[index]=(json.dumps(updated,ensure_ascii=False,allow_nan=False)+'\n').encode()
    temporary=folder/'records.recovery.tmp'
    with temporary.open('wb') as stream:
        stream.write(b''.join(lines));stream.flush();os.fsync(stream.fileno())
    temporary.replace(folder/'records.jsonl')
    records=read_rows(folder/'records.jsonl')
    assert all(before==after for i,(before,after) in enumerate(zip(rows,records)) if i!=index)
    assert file_hash(folder/'generations.jsonl')==generation_hash
    summary=artifacts.publish(folder,manifest,records)
    (folder/'repeatability.json').write_text(json.dumps(artifacts.rescore(folder),indent=2)+'\n')
    details={'record_id':original['record_id'],'arm':'baseline','user_authorized_single_recovery':True,
             'original_exception_message_retained':False,'original_judge_error':'ValueError',
             'judge_function':'copilot.evaluation.judge.evaluate','calls':calls,
             'new_answer_generation_calls':0,'new_retrieval_calls':0,'other_records_unchanged':len(records)-1,
             'generations_sha256_unchanged':generation_hash,'implementation_sha256_unchanged':implementation_hash(),
             'gt_sha256_unchanged':file_hash(WORKBOOK),'judge_trace_id':capture.trace_id,
             'judge_usage':capture.summary,'judge_latency_ms':elapsed,'judge_spans':list(capture.spans.values()),
             'judgement':result.model_dump(),'metrics':updated['metrics'],'final_errors':summary['errors']}
    (audit/'recovery.json').write_text(json.dumps(details,indent=2)+'\n')
    provider().force_flush(timeout_millis=40000)
    print(json.dumps({k:details[k] for k in ('record_id','new_answer_generation_calls','new_retrieval_calls','other_records_unchanged','final_errors','judgement')}))


if __name__=='__main__':
    main()
