"""Score all locked candidate working cases after exact-reuse and fresh semantic review."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

WORK = Path(__file__).resolve().parent
REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')
OUT = REPO / 'copilot/response_drafting/results/activity-14/workflow-review'
sys.path.insert(0, str(REPO))
from copilot.diagnostics.evaluation import bind_review, score_bound_review


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def score_subset(rows, labels, decisions):
    with TemporaryDirectory(prefix='candidate-bound-score-') as temp:
        p, g = Path(temp) / 'predictions.jsonl', Path(temp) / 'gold.json'
        p.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
        write(g, {'cases': labels})
        bound = bind_review(p, g, decisions, reviewer='Assistant semantic review; unchanged subgroup judgements')
        return score_bound_review(p, g, bound)['candidate']


def main():
    gold_path, raw_path = OUT / 'original-working-reference.json', OUT / 'candidate/predictions.jsonl'
    preparation = json.loads((OUT / 'candidate-review-preparation.json').read_text())
    assert preparation['gold_sha256'] == digest(gold_path)
    assert preparation['candidate_predictions_sha256'] == digest(raw_path)
    labels = {row['record_id']: row for row in json.loads(gold_path.read_text())['cases']}
    raw = list(map(json.loads, raw_path.read_text().splitlines()))
    by_id = {row['record_id']: row for row in raw}
    inputs = json.loads((OUT / 'inputs317.json').read_text())
    ordered_ids = [row['record_id'] for row in inputs]
    assert len(raw) == len(by_id) == len(labels) == len(ordered_ids) == 317
    assert set(by_id) == set(labels) == set(ordered_ids)
    reused = json.loads((OUT / 'candidate-reused-judgements.json').read_text())
    decisions = {row['record_id']: row for row in reused}
    batches = {}
    fresh_count = 0
    for number in (1, 2):
        path = WORK / f'candidate-review-{number}.json'
        batches[path.name] = digest(path)
        for row in json.loads(path.read_text()):
            assert row['record_id'] not in decisions
            decisions[row['record_id']] = {**row, 'review_origin': 'fresh_assistant_semantic_review'}
            fresh_count += 1
    assert len(decisions) == 317 and set(decisions) == set(labels)
    projected, reviews = [], []
    for rid in ordered_ids:
        row, expected, reviewed = by_id[rid], labels[rid], decisions[rid]
        assert reviewed['questions_sha256'] == value_hash(row['questions']), rid
        assert reviewed['gold_sha256'] == value_hash(expected['questions']), rid
        projected.append({'record_id': rid, 'group': row['group'], 'fold': row['fold'],
                          'bucket': expected['bucket'], 'questions': {'candidate': row['questions']}})
        reviews.append({key: reviewed[key] for key in ['record_id', 'questions_sha256', 'gold_sha256', 'reason', 'review_origin']})
        reviews[-1]['methods'] = {'candidate': {key: reviewed[key] for key in ['whole', 'facts']}}
    projected_path = OUT / 'candidate-score-predictions.jsonl'
    projected_path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in projected))
    bound = bind_review(projected_path, gold_path, reviews,
                        reviewer='Assistant semantic review; exact text reuse and deterministic zero matches for empty-side cases')
    bound['review_kind'] = 'Assistant semantic review, not independent human acceptance.'
    bound['source_full_predictions_sha256'] = preparation['candidate_predictions_sha256']
    bound['review_batches_sha256'] = batches
    bound['scope'] = 'All 317 fixed working-eval cases; retrospective grouped folds; frozen and holdout excluded.'
    review_path = OUT / 'candidate-bound-review.json'
    write(review_path, bound)
    overall = score_bound_review(projected_path, gold_path, bound)['candidate']
    buckets, folds = {}, {}
    for dimension, output in [('bucket', buckets), ('fold', folds)]:
        for value in sorted({row[dimension] for row in projected}):
            selected = [row for row in projected if row[dimension] == value]
            ids = {row['record_id'] for row in selected}
            metrics = score_subset(selected, [labels[rid] for rid in ordered_ids if rid in ids],
                                   [row for row in reviews if row['record_id'] in ids])
            output[str(value)] = {'cases': len(selected), 'groups': len({row['group'] for row in selected}), **metrics}
    baseline = json.loads((OUT / 'baseline-score.json').read_text())['overall']
    report = {'method': 'candidate', 'cases': 317, 'groups': len({row['group'] for row in projected}),
              'gold_positive_cases': sum(bool(row['questions']) for row in labels.values()),
              'predicted_positive_cases': sum(bool(row['questions']) for row in raw),
              'gold_empty_cases_with_questions': sum(bool(row['questions']) and not labels[row['record_id']]['questions'] for row in raw),
              'fresh_semantic_cases': fresh_count, 'reused_semantic_cases': preparation['counts']['identical_questions'] + preparation['counts']['reordered_identical_questions'],
              'deterministic_empty_side_cases': preparation['counts']['empty_side'],
              'overall': overall, 'baseline_overall': baseline,
              'delta': {key: overall[key] - baseline[key] for key in ['f1', 'precision', 'recall', 'fact_recall', 'questions_on_empty_gold']},
              'by_bucket': buckets, 'by_fold': folds,
              'fold_interpretation': 'Retrospective robustness on existing grouped working folds, not unseen validation.',
              'review_kind': bound['review_kind'], 'frozen_cases': 0, 'holdout_cases': 0,
              'source_full_predictions_sha256': digest(raw_path), 'score_predictions_sha256': digest(projected_path),
              'gold_sha256': digest(gold_path), 'bound_review_sha256': digest(review_path),
              'route_counts': dict(Counter(row['snapshot']['route'] for row in raw)),
              'schema_valid_cases': sum(not row['schema_errors'] for row in raw)}
    write(OUT / 'candidate-score.json', report)
    print(json.dumps({key: report[key] for key in ['cases', 'gold_empty_cases_with_questions', 'overall', 'delta']}, indent=2))


if __name__ == '__main__':
    main()
