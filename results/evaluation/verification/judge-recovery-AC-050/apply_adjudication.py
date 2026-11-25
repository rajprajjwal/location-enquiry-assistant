"""Apply the approved citation-only adjudication to the saved failed result."""
from datetime import datetime, timezone
from pathlib import Path
import json
import os

from copilot.evaluation import artifacts
from copilot.evaluation.contracts import Judgement, Prediction
from copilot.evaluation.data import digest, file_hash, WORKBOOK
from copilot.evaluation.runner import implementation_hash, read_rows
from copilot.evaluation.scoring import citation_evidence, metrics


def main():
    root=Path('results/evaluation')
    folder=root/'holdout-final'
    audit=root/'verification/judge-recovery-AC-050'
    if (audit/'adjudication.json').exists():
        raise ValueError('This adjudication has already been recorded')
    locked=json.loads((root/'locked-selection.json').read_text())
    manifest=json.loads((folder/'manifest.json').read_text())
    assert implementation_hash()==locked['implementation_sha256']
    assert file_hash(WORKBOOK)==locked['workbook_sha256']
    for key,path in [('corpus_sha256','copilot/rag/data/processed/chunks.jsonl'),
                     ('rates_sha256','copilot/config/observability.yaml')]:
        assert file_hash(Path(path))==manifest['binding'][key]
    resources=json.loads((root/'resource-binding.json').read_text())['tracked_resources_sha256']
    assert all(file_hash(Path(p))==h for p,h in resources.items())
    before={p.as_posix():file_hash(p) for name in ('working-contract-validation','frozen-paired','holdout-final')
            for p in (root/name).iterdir() if p.is_file() and p.suffix in ('.json','.jsonl')}
    lines=(folder/'records.jsonl').read_bytes().splitlines(keepends=True)
    rows=[json.loads(line) for line in lines]
    index=next(i for i,r in enumerate(rows) if (r['record_id'],r['arm'])==('GT-LBS-AC-050','baseline'))
    original=rows[index]
    assert original==json.loads((audit/'original-record.json').read_text())
    assert original.get('judge_error')=='ValueError'
    failure=json.loads((audit/'retry-failure.json').read_text())
    raw=json.loads(failure['calls'][0]['response_text'])
    assert raw['citation_supported']==[]
    body={**raw,'citation_supported':[False]}
    judgement=Judgement.model_validate(body)
    case=next(c for c in read_rows(folder/'cases.jsonl') if c['record_id']==original['record_id'])
    assert digest(read_rows(folder/'cases.jsonl'))==manifest['binding']['cases_sha256']
    evidence,bound=citation_evidence(Prediction.model_validate(original['prediction']),original['retrieved_evidence'])
    assert len(original['prediction']['citations'])==1 and bound==[False] and not evidence
    approval={'type':'explicit project-owner citation-format adjudication',
              'authorization':'Okay, please record the audited [false] citation adjudication for AC-050, update the final scores and report, and keep the locked configuration and GT unchanged.',
              'scope':'GT-LBS-AC-050 baseline citation_supported only',
              'original_flags':[],'adjudicated_flags':[False],
              'reason':'The single predicted citation has no verified supporting evidence.',
              'audit_path':str(audit/'adjudication.json')}
    updated={**original,'judgement':judgement.model_dump(),'judgement_adjudication':approval,
             'judge_attempt_history':{'original_error':'ValueError','retry_error':failure['message'],
                                      'retry_audit':str(audit/'retry-failure.json'),
                                      'retry_usage_and_latency_available':False}}
    updated.pop('judge_error')
    updated['metrics']=metrics(case,updated,judgement,bound)
    assert updated['prediction']==original['prediction']
    lines[index]=(json.dumps(updated,ensure_ascii=False,allow_nan=False)+'\n').encode()
    temporary=folder/'records.adjudication.tmp'
    with temporary.open('wb') as stream:
        stream.write(b''.join(lines));stream.flush();os.fsync(stream.fileno())
    temporary.replace(folder/'records.jsonl')
    records=read_rows(folder/'records.jsonl')
    assert all(a==b for i,(a,b) in enumerate(zip(rows,records)) if i!=index)
    summary=artifacts.publish(folder,manifest,records)
    summary['adjudications']=[approval]
    summary['automatic_judge_failures_resolved_by_adjudication']=1
    (folder/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (folder/'repeatability.json').write_text(json.dumps(artifacts.rescore(folder),indent=2)+'\n')
    mutable={str(folder/p) for p in ('records.jsonl','summary.json','repeatability.json')}
    assert all(file_hash(Path(p))==h for p,h in before.items() if p not in mutable)
    result={'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'approval':approval,
            'raw_judge_result':raw,'accepted_judgement':judgement.model_dump(),
            'numeric_scores_and_reasons_unchanged':True,'prediction_unchanged':True,
            'other_holdout_records_unchanged':len(records)-1,'all_generation_journals_unchanged':True,
            'frozen_and_working_results_unchanged':True,'implementation_unchanged':True,'gt_unchanged':True,
            'new_endpoint_calls':0,'before_file_sha256':before,
            'before_metrics':original['metrics'],'after_metrics':updated['metrics'],
            'unresolved_final_errors':summary['errors'],'adjudicated_judgements':1,
            'overhead_note':'Existing judge overhead retains the original failed attempt only; retry usage/latency were not retained and are not fabricated.'}
    (audit/'adjudication.json').write_text(json.dumps(result,indent=2)+'\n')
    ledger_path=root/'holdout-ledger.json'
    ledger=json.loads(ledger_path.read_text())
    ledger['previous_completion_state']=ledger['state']
    ledger.update(state='completed_with_adjudication',adjudications=[approval],unresolved_errors=0)
    ledger_path.write_text(json.dumps(ledger,indent=2)+'\n')
    print(json.dumps({'unresolved_errors':summary['errors'],'adjudications':1,'new_endpoint_calls':0}))


if __name__=='__main__':
    main()
