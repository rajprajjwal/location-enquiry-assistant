"""Select a plain-model strategy on grouped working-eval only."""
import argparse
import json
from pathlib import Path
from .baselines import STRATEGIES
from .data import read_cases,sample,file_hash,digest,WORKBOOK
from copilot.paths import REPO_ROOT
from .runner import run,implementation_hash
from .artifacts import rescore


def select(output,mode='hybrid',per_bucket=1):
    cases=sample(read_cases(),per_bucket)
    rows=[]
    for strategy in STRATEGIES:
        summary=run(output/strategy,cases,strategy=strategy,mode=mode,arms=('baseline',))
        score=next(r for r in summary['metrics'] if r['dimension']=='overall' and r['metric']=='answer_accuracy')
        rows.append({'strategy':strategy,'accuracy':score['score'],'scored':score['scored'],
                     'errors':summary['errors'],'metrics_sha256':summary['metrics_sha256']})
    valid=[r for r in rows if r['errors']==0 and r['scored']==len(cases)]
    if not valid:
        raise ValueError('No completely scored baseline strategy')
    # Stable strategy order resolves equal quality without looking at frozen cases.
    best=max(valid,key=lambda r:r['accuracy'])
    result={'strategy':best['strategy'],'selection_split':'working_eval','case_ids':[c['record_id'] for c in cases],
            'excluded_validation_groups':[c['group'] for c in cases], 'candidates':rows,
            'implementation_sha256':implementation_hash(),'retrieval':mode,
            'workbook_sha256':file_hash(WORKBOOK),
            'corpus_sha256':file_hash(REPO_ROOT/'copilot/rag/data/processed/chunks.jsonl'),
            'locked':False,'repeatability_passed':all(rescore(output/r['strategy'])['passed'] for r in rows),
            'selection_rule':'Highest automatic rubric accuracy; ties use declared strategy order. Frozen and holdout excluded.'}
    (output/'selection.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--mode',choices=['bm25','hybrid'],default='hybrid')
    parser.add_argument('--per-bucket',type=int,default=1)
    args=parser.parse_args()
    print(json.dumps(select(args.out,args.mode,args.per_bucket)))
