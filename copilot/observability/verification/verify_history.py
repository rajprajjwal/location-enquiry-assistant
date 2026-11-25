"""Compare existing trace IDs and saved reports without generating answers."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit
import httpx

from copilot.observability.langfuse_local import load_environment
from copilot.observability.langfuse_migration import checksum
from copilot.paths import REPO_ROOT


def collect(client,trace_id,started):
    params={'traceId':trace_id,'fromStartTime':started,'toStartTime':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),
            'fields':'core','limit':1000}
    ids=set()
    while True:
        response=client.get('/api/public/v2/observations',params=params)
        response.raise_for_status()
        body=response.json()
        ids.update(r['id'] for r in body.get('data',[]))
        cursor=body.get('meta',{}).get('cursor')
        if not cursor:
            return sorted(ids)
        params['cursor']=cursor


def verify(env_file,root,out,reference=None):
    values=load_environment(env_file)
    url=urlsplit(values['LANGFUSE_BASE_URL'])
    if url.scheme!='https' and not (url.scheme=='http' and url.hostname in ('localhost','127.0.0.1')):
        raise ValueError('History verification requires HTTPS or localhost')
    result={'scope':'Two saved generation traces per final run; report checksums for both final runs.',
            'model_calls':0,'new_traces_created':0,'report_sha256':{},'observations':{}}
    with httpx.Client(base_url=values['LANGFUSE_BASE_URL'],
                     auth=(values['LANGFUSE_PUBLIC_KEY'],values['LANGFUSE_SECRET_KEY']),timeout=30) as client:
        for name in ('frozen-paired','holdout-final'):
            folder=Path(root)/name
            for filename in ('manifest.json','cases.jsonl','generations.jsonl','records.jsonl','summary.json'):
                result['report_sha256'][name+'/'+filename]=checksum(folder/filename)
            manifest=json.loads((folder/'manifest.json').read_text())
            started=(datetime.fromisoformat(manifest['started_at'])-timedelta(days=1)).isoformat()
            records=[json.loads(l) for l in (folder/'generations.jsonl').read_text().splitlines()]
            traces=list(dict.fromkeys(r['trace_id'] for r in records if r.get('trace_id')))[:2]
            if len(traces)!=2:
                raise ValueError('Expected two saved generation trace IDs in '+name)
            for trace_id in traces:
                ids=collect(client,trace_id,started)
                if not ids:
                    raise ValueError('Historical trace is missing: '+trace_id)
                result['observations'][trace_id]=ids
    if reference:
        original=json.loads(Path(reference).read_text())
        for key in ('report_sha256','observations'):
            if result[key]!=original[key]:
                raise ValueError('History comparison failed: '+key)
    result['passed']=True
    out=Path(out)
    with out.open('x') as stream:
        stream.write(json.dumps(result,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',type=Path,required=True)
    parser.add_argument('--root',type=Path,default=REPO_ROOT/'results/evaluation')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--reference',type=Path)
    args=parser.parse_args()
    result=verify(args.env_file,args.root,args.out,args.reference)
    print(json.dumps({'passed':result['passed'],'sampled_traces':len(result['observations']),'model_calls':0}))


if __name__=='__main__':
    main()
