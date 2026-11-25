"""Rescore saved working generations after a scorer fix without regenerating."""
from pathlib import Path
import json
from time import perf_counter
from .scoring import qualification_checks
from copilot.model_gateway.client import LLMClient
from copilot.observability import trace_run
from . import artifacts,judge
from .contracts import Prediction
from .data import digest
from .runner import read_rows,append,implementation_hash
from .scoring import citation_evidence,metrics


def rejudge(source,output):
    manifest=json.loads((source/'manifest.json').read_text())
    if manifest['split']!='working_eval':
        raise ValueError('Scorer development is restricted to working-eval')
    cases=read_rows(source/'cases.jsonl')
    if digest(cases)!=manifest['binding']['cases_sha256']:
        raise ValueError('Saved working references changed')
    originals=read_rows(source/'generations.jsonl')
    expected={(c['record_id'],arm) for c in cases for arm in manifest['binding']['arms']}
    if {(r['record_id'],r['arm']) for r in originals}!=expected or len(originals)!=len(expected):
        raise ValueError('Source generations are incomplete or duplicated')
    if output.exists():
        return artifacts.load(output)
    output.mkdir(parents=True)
    new_manifest={**manifest,'generation_source':str(source),'generation_implementation_sha256':manifest['binding']['implementation_sha256'],
                  'new_generation_calls':0,'binding':{**manifest['binding'],'implementation_sha256':implementation_hash()}}
    (output/'manifest.json').write_text(json.dumps(new_manifest,indent=2)+'\n')
    (output/'cases.jsonl').write_text((source/'cases.jsonl').read_text())
    by_id={c['record_id']:c for c in cases}
    previous={(r['record_id'],r['arm']):r for r in read_rows(source/'records.jsonl')}
    records=[]
    for original in originals:
        row={**previous.get((original['record_id'],original['arm']),{}),**original}
        row.pop('judge_error',None)
        case=by_id[row['record_id']]
        judgement=None
        bound=[]
        if row.get('prediction'):
            prediction=Prediction.model_validate(row['prediction'])
            evidence,bound=citation_evidence(prediction,row.get('retrieved_evidence',[]))
            started=perf_counter()
            try:
                with trace_run(metadata={'record_id':row['record_id'],'bucket':row['bucket'],'split':'working_eval','run_id':output.name}) as capture:
                    judgement=judge.evaluate(case,prediction,evidence)
                row.update(judgement=judgement.model_dump(),judge_usage=capture.summary,judge_latency_ms=(perf_counter()-started)*1000)
            except Exception as error:
                row['judge_error']=type(error).__name__
        if row.get('prediction'):
            row['qualification_checks']=qualification_checks(row['prediction']['qualification'],case['gold']['outputs']['qualification_details'])
        row['citation_source_binding']=bound
        row['metrics']=metrics(case,row,judgement,bound)
        append(output/'records.jsonl',row)
        records.append(row)
        print(output.name+' '+row['record_id']+' rescored',flush=True)
    summary=artifacts.publish(output,new_manifest,records)
    (output/'repeatability.json').write_text(json.dumps(artifacts.rescore(output),indent=2)+'\n')
    return summary
