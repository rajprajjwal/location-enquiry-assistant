"""Measure fresh-judge score variation on saved working predictions."""
import argparse
import json
from pathlib import Path
from copilot.observability import trace_run
from .contracts import Prediction
from .judge import evaluate
from .scoring import citation_evidence,metrics
from .artifacts import aggregate,load

QUALITY=('answer_accuracy','grounding','comparison_completeness','qualification_completeness','history_use','citation_precision','citation_coverage')


def verify(folder,output):
    saved=load(folder)
    if saved['manifest']['split']!='working_eval':
        raise ValueError('Fresh judging is restricted to working-eval')
    cases={c['record_id']:c for c in map(json.loads,(folder/'cases.jsonl').read_text().splitlines())}
    rows=[json.loads(l) for l in (folder/'records.jsonl').read_text().splitlines()]
    repeated=[]
    for row in rows:
        if row.get('prediction') is None:
            repeated.append(row)
            continue
        case=cases[row['record_id']]
        prediction=Prediction.model_validate(row['prediction'])
        evidence,bound=citation_evidence(prediction,row.get('retrieved_evidence',[]))
        with trace_run(metadata={'record_id':row['record_id'],'bucket':row['bucket'],'split':'working_eval','run_id':'fresh-judge-repeatability'}):
            judgement=evaluate(case,prediction,evidence)
        duplicate={**row,'judgement':judgement.model_dump()}
        duplicate['metrics']=metrics(case,duplicate,judgement,bound)
        repeated.append(duplicate)
        print(row['record_id']+' '+row['arm']+' reviewed again',flush=True)
    before={(r['arm'],r['dimension'],r['value'],r['metric']):r['score'] for r in saved['metrics']}
    differences=[]
    for r in aggregate(repeated):
        key=r['arm'],r['dimension'],r['value'],r['metric']
        if r['metric'] in QUALITY and r['score'] is not None and before.get(key) is not None:
            differences.append({'arm':r['arm'],'dimension':r['dimension'],'value':r['value'],'metric':r['metric'],
                                'absolute_delta':abs(r['score']-before[key])})
    report={'split':'working_eval','records':len(rows),'maximum_delta':max((r['absolute_delta'] for r in differences),default=0),
            'overall_maximum_delta':max((r['absolute_delta'] for r in differences if r['dimension']=='overall'),default=0),
            'tolerance':.01,'passed':all(r['absolute_delta']<=.01 for r in differences),
            'scope':'Fresh automatic judgement on identical saved predictions and evidence; generation not repeated.',
            'differences':differences}
    output.write_text(json.dumps(report,indent=2)+'\n')
    output.with_name(output.stem+'-records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in repeated))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(verify(args.run,args.out)))
