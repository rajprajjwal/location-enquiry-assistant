"""Recompute scores from the saved predictions and prediction-bound review."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from copilot.diagnostics.evaluation import bind_review, score_bound_review


def rescore(folder):
    predictions, gold = folder / 'predictions.jsonl', folder / 'locked-gold.json'
    review = json.loads((folder / 'question-review.bound.json').read_text())
    scores = {'combined': score_bound_review(predictions, gold, review)}
    rows = [json.loads(line) for line in predictions.read_text().splitlines()]
    labels = json.loads(gold.read_text())['cases']
    for cohort in ('original16', 'fresh16'):
        selected = [row for row in rows if row['cohort'] == cohort]
        ids = {row['record_id'] for row in selected}
        with TemporaryDirectory() as temp:
            pred, target = Path(temp) / 'predictions.jsonl', Path(temp) / 'gold.json'
            pred.write_text(''.join(json.dumps(row) + '\n' for row in selected))
            target.write_text(json.dumps({'cases': [row for row in labels if row['record_id'] in ids]}))
            subset = bind_review(pred, target, [row for row in review['cases'] if row['record_id'] in ids], reviewer=review['reviewer'])
            scores[cohort] = score_bound_review(pred, target, subset)
    return scores


if __name__ == '__main__':
    print(json.dumps(rescore(Path(__file__).resolve().parent), indent=2))
