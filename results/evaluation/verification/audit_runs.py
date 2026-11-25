"""Verify completed evaluation artifacts without making endpoint requests."""
from pathlib import Path
import json

from copilot.evaluation.artifacts import load,rescore
from copilot.evaluation.contracts import Judgement,METRICS
from copilot.evaluation.data import digest,file_hash,WORKBOOK
from copilot.evaluation.runner import implementation_hash
from copilot.evaluation.scoring import metrics


def audit(folder):
    summary=load(folder)
    cases=[json.loads(line) for line in (folder/'cases.jsonl').read_text().splitlines()]
    records=[json.loads(line) for line in (folder/'records.jsonl').read_text().splitlines()]
    generations=[json.loads(line) for line in (folder/'generations.jsonl').read_text().splitlines()]
    expected={(case['record_id'],arm) for case in cases for arm in ('baseline','agent')}
    assert {(r['record_id'],r['arm']) for r in records}==expected
    assert {(r['record_id'],r['arm']) for r in generations}==expected
    assert len(records)==len(generations)==len(expected)
    assert digest(cases)==summary['manifest']['binding']['cases_sha256']
    by_id={case['record_id']:case for case in cases}
    for row in records:
        case=by_id[row['record_id']]
        assert all(row[key]==case[key] for key in ('bucket','api','team','split'))
        judgement=Judgement.model_validate(row['judgement']) if row.get('judgement') else None
        assert digest(metrics(case,row,judgement,row.get('citation_source_binding',[])))==digest(row['metrics'])
        if row['arm']=='baseline':
            assert not row['tool_calls']
        for key,(_,unit,_) in METRICS.items():
            value=row['metrics'].get(key)
            if unit=='ratio' and value is not None:
                assert 0<=value<=1
    assert rescore(folder)['passed']
    return {'cases':len(cases),'arm_records':len(records),'unique_generations':len(generations),
            'per_record_score_recomputation':'identical','aggregate_recomputation':'identical',
            'duplicate_or_foreign_records':0,'endpoint_calls':0}


if __name__=='__main__':
    root=Path('results/evaluation')
    selection=json.loads((root/'locked-selection.json').read_text())
    assert selection['implementation_sha256']==implementation_hash()
    assert selection['workbook_sha256']==file_hash(WORKBOOK)
    result={'runs':{name:audit(root/name) for name in ('working-contract-validation','frozen-paired','holdout-final')
                    if (root/name/'summary.json').exists()},
            'source_lock_unchanged':True,'gt_unchanged':True,'endpoint_calls':0}
    if (root/'holdout-ledger.json').exists():
        ledger=json.loads((root/'holdout-ledger.json').read_text())
        approved=json.loads((root/'holdout-review.json').read_text())
        exclusions=json.loads((root/'verification/leakage-readiness.json').read_text())['excluded_holdout_ids']
        assert set(approved['case_ids'])-set(ledger['binding']['case_ids'])==set(exclusions)
        result['holdout_exclusions_match_approval']=True
    (root/'verification/artifact-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
