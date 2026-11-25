"""Lock a selection only after separate working groups and repeat checks pass."""
import argparse
import json
from pathlib import Path
from .artifacts import load,rescore
from .data import file_hash
from .runner import implementation_hash


def lock(selection,validation,judges,output):
    chosen=json.loads(selection.read_text())
    fresh=json.loads(judges.read_text())
    run=load(validation)
    binding=run['manifest']['binding']
    if run['manifest']['split']!='working_eval' or run['errors'] or run['paired_cases']!=run['cases']:
        raise ValueError('Lock requires a complete paired working-eval validation run')
    if chosen['implementation_sha256']!=implementation_hash() or binding['implementation_sha256']!=implementation_hash():
        raise ValueError('The implementation changed after selection or validation')
    if chosen['strategy']!=binding['strategy']:
        raise ValueError('Validation did not use the selected baseline')
    cases=[json.loads(l) for l in (validation/'cases.jsonl').read_text().splitlines()]
    if {c['group'] for c in cases}&set(chosen['excluded_validation_groups']):
        raise ValueError('Validation groups overlap baseline selection')
    if not fresh.get('passed') or not rescore(validation)['passed']:
        raise ValueError('The fresh-judge or artifact repeatability check did not pass')
    result={**chosen,'locked':True,'repeatability_passed':True,'fresh_judge_repeatability_passed':True,
            'validation_summary_sha256':file_hash(validation/'summary.json'),
            'judge_repeatability_sha256':file_hash(judges)}
    output.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection',required=True,type=Path)
    parser.add_argument('--validation',required=True,type=Path)
    parser.add_argument('--judges',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(lock(args.selection,args.validation,args.judges,args.out)))
