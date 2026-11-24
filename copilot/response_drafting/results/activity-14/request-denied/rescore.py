"""Reproduce saved overall and cohort question scores from bound judgements."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from copilot.diagnostics.evaluation import bind_review, score_bound_review


def rescore(folder):
    pred, gold = folder / 'predictions.jsonl', folder / 'locked-gold.json'
    review = json.loads((folder / 'question-review.bound.json').read_text())
    scores = {'combined52': score_bound_review(pred, gold, review)}
    rows = [json.loads(line) for line in pred.read_text().splitlines()]
    labels = json.loads(gold.read_text())['cases']
    cohorts = {'previous32': {'original16', 'fresh16'}, 'separate20': {'separate20'}}
    for name, included in cohorts.items():
        selected = [row for row in rows if row['cohort'] in included]
        ids = {row['record_id'] for row in selected}
        with TemporaryDirectory() as temp:
            predictions, target = Path(temp) / 'predictions.jsonl', Path(temp) / 'gold.json'
            predictions.write_text(''.join(json.dumps(row) + '\n' for row in selected))
            target.write_text(json.dumps({'cases': [row for row in labels if row['record_id'] in ids]}))
            subset = bind_review(predictions, target, [row for row in review['cases'] if row['record_id'] in ids], reviewer=review['reviewer'])
            scores[name] = score_bound_review(predictions, target, subset)
    return scores


if __name__ == '__main__':
    print(json.dumps(rescore(Path(__file__).resolve().parent), indent=2))
