"""Check judge calibration and fresh-call stability on working-eval only."""
import argparse
import json
from pathlib import Path
from copilot.model_gateway.client import LLMClient
from copilot.observability import trace_run
from .contracts import Prediction
from .data import read_cases,sample,digest
from .judge import evaluate


def reference_prediction(case):
    gold=case['gold']
    outputs=gold['outputs']
    return Prediction(answer=outputs['response_draft']['draft_text'],
        citations=[{k:c[k] for k in ('url','span','supports_claim')} for c in outputs['response_draft']['citations']],
        clarifying_questions=[q['text'] for q in outputs['clarifying_questions']['questions']],
        qualification=outputs['qualification_details'],comparison=outputs['comparison'],
        owner=outputs['responsible_role']['owner'],next_action=outputs['next_action']['action_type'],
        should_escalate=outputs['responsible_role']['should_escalate'],record_update=outputs['proposed_record_update'],
        intent=gold['intent'],api=case['api'],team=case['team'])


def check(output,count=3):
    client=LLMClient()
    cases=sample(read_cases())[:count]
    results=[]
    for case in cases:
        positive=reference_prediction(case)
        evidence=[{'url':c.url,'text':c.span} for c in positive.citations]
        blank=positive.model_copy(update={'answer':'','citations':[],'clarifying_questions':[],
                                         'qualification':{},'comparison':{},'owner':None,'next_action':None})
        scores=[]
        for name,prediction in [('reference',positive),('reference_repeat',positive),('blank',blank)]:
            print(f'{case["record_id"]}: {name}',flush=True)
            with trace_run(metadata={'record_id':case['record_id'],'bucket':case['bucket'],'split':'working_eval','run_id':'judge-calibration'}) as capture:
                result=evaluate(case,prediction,list(evidence),client)
            scores.append({'name':name,'judgement':result.model_dump(),'usage':capture.summary})
        first,second,negative=[r['judgement'] for r in scores]
        delta=max(abs(first[k]-second[k]) for k in ('answer_accuracy','grounding','comparison_completeness','qualification_completeness','history_use'))
        results.append({'record_id':case['record_id'],'reference_accuracy':first['answer_accuracy'],
                        'blank_accuracy':negative['answer_accuracy'],'max_fresh_judge_delta':delta,'scores':scores})
    report={'split':'working_eval','cases':len(cases),'checks':results,
            'calibration_passed':all(r['reference_accuracy']>=.95 and r['blank_accuracy']<=.05 for r in results),
            'fresh_judge_repeatability_passed':all(r['max_fresh_judge_delta']<=.01 for r in results),
            'scope':'Positive/empty controls using supplied reference citations. This does not establish human agreement or independent source verification.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    check(args.out)
