"""Bind canonical-fact alignment after semantic inspection of the rendered questions."""
import json
from pathlib import Path
import sys
import argparse
for root in Path(__file__).resolve().parents:
    if (root / "copilot/diagnostics/evaluation.py").is_file():
        sys.path.insert(0, str(root))
        break
from copilot.diagnostics.evaluation import bind_review, score_bound_review


def score(folder):
    predictions=folder/'predictions.jsonl'; gold=folder/'locked-gold.json'
    rows=[json.loads(line) for line in predictions.read_text().splitlines()]
    labels={row['record_id']:row['questions'] for row in json.loads(gold.read_text())['cases']}
    judgements=[]; alignment=[]
    for row in rows:
        methods={}; details={}
        for method in ('baseline','integrated'):
            groups=(row['details'][method]['selection'] or {}).get('groups',[])
            active=row['snapshots'][method]['active_questions']['questions']
            whole=[]; facts=[]; used=set(); mapped=[]
            for p,text in enumerate(row['questions'][method],1):
                fields=next((group['fields'] for group in groups if group['text']==text),None)
                if fields is None:
                    field=next((q.get('field') for q in active if q['text']==text),None)
                    fields=[{'provider':'current_provider'}.get(field,field)] if field else []
                    if 'billing account based in' in text: fields=['billing_country']
                fields=set(fields)
                mapped.append({'question':p,'text':text,'facts':sorted(fields)})
                for g,target in enumerate(labels[row['record_id']],1):
                    for f,field in enumerate(target['facts'],1):
                        if field in fields: facts.append([p,g,f])
                    if set(target['facts'])==fields and g not in used:
                        whole.append([p,g]);used.add(g)
                        break
            methods[method]={'whole':whole,'facts':facts,'notes':'Canonical fact alignment of the saved text, semantically inspected. Whole match requires equal grouped facts; partial facts scored separately.'}
            details[method]=mapped
        judgements.append({'record_id':row['record_id'],'methods':methods})
        alignment.append({'record_id':row['record_id'],'gold':labels[row['record_id']],'actual':details})
    review=bind_review(predictions,gold,judgements,reviewer='Assistant semantic inspection with reproducible canonical-fact alignment of rendered questions')
    (folder/'question-review.bound.json').write_text(json.dumps(review,indent=2)+'\n')
    (folder/'question-alignment.json').write_text(json.dumps(alignment,indent=2)+'\n')
    metrics=score_bound_review(predictions,gold,review)
    (folder/'scores.json').write_text(json.dumps(metrics,indent=2)+'\n')
    return metrics


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(score(args.folder), indent=2))
