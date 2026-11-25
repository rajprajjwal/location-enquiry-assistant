"""Versioned run artifacts are the shared harness and dashboard contract."""
from collections import defaultdict
from statistics import mean
import json
from pathlib import Path
from .contracts import METRICS
from .data import digest

SCHEMA_VERSION = '1.0'


def aggregate(records):
    groups = defaultdict(list)
    for row in records:
        for dimension,value in [('overall','all'), *[(d,row[d]) for d in ('bucket','api','team')]]:
            groups[row['arm'],dimension,value].append(row)
    output = []
    for (arm,dimension,value),rows in sorted(groups.items()):
        for key in METRICS:
            numbers = [r['metrics'][key] for r in rows if r['metrics'].get(key) is not None]
            weights = [len(r.get('prediction',{}).get('citations',[])) if key=='citation_precision' else
                       len(r.get('tool_calls',[])) if key=='tool_execution_success' else 1
                       for r in rows if r['metrics'].get(key) is not None]
            denominator=sum(weights)
            total=sum(v*w for v,w in zip(numbers,weights))
            output.append({'arm':arm,'dimension':dimension,'value':value,'metric':key,
                           'score':total/denominator if denominator else None,'scored':len(numbers),'cases':len(rows),
                           'unit_denominator':denominator,'sum':total if numbers else None})
    return output


def publish(folder,manifest,records):
    pairs = {(r['record_id'],r['arm']) for r in records}
    if len(pairs)!=len(records):
        raise ValueError('Duplicate record/arm artifacts')
    summary = {'schema_version':SCHEMA_VERSION,'run_id':folder.name,'manifest':manifest,
               'records':len(records),'cases':len({r['record_id'] for r in records}),
               'paired_cases':sum(all((identifier,arm) in pairs for arm in ('baseline','agent')) for identifier in {r['record_id'] for r in records}),
               'errors':sum(bool(r.get('generation_error') or r.get('judge_error') or r.get('retrieval_error')) for r in records),
               'metric_catalog':{k:{'label':v[0],'unit':v[1],'higher_is_better':v[2]} for k,v in METRICS.items()},
               'metrics':aggregate(records)}
    summary['metrics_sha256']=digest(summary['metrics'])
    temporary = folder/'summary.tmp'
    temporary.write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    temporary.replace(folder/'summary.json')
    return summary


def load(folder):
    folder=Path(folder)
    summary=json.loads((folder/'summary.json').read_text())
    if summary.get('schema_version')!=SCHEMA_VERSION or digest(summary['metrics'])!=summary['metrics_sha256']:
        raise ValueError('Unsupported or changed evaluation summary')
    return summary


def rescore(folder):
    folder=Path(folder)
    previous=load(folder)
    records=[json.loads(l) for l in (folder/'records.jsonl').read_text().splitlines()]
    observed=aggregate(records)
    if digest(observed)!=previous['metrics_sha256']:
        raise ValueError('Saved metrics differ from the bound per-record scores')
    return {'passed':True,'metric_delta':0,'endpoint_calls':0,'scope':'Deterministic saved-artifact aggregation; not fresh-inference stability.'}
