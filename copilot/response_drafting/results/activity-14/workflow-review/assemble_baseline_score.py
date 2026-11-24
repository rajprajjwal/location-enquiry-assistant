"""Bind all working baseline judgements and score with the production scorer."""
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


def score_subset(rows, labels, reviews):
    with TemporaryDirectory(prefix='working-bound-score-') as temp:
        root = Path(temp)
        p, g = root / 'predictions.jsonl', root / 'gold.json'
        p.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
        write(g, {'cases': labels})
        review = bind_review(p, g, reviews, reviewer='Assistant semantic review; unchanged subgroup judgements')
        return score_bound_review(p, g, review)['baseline']


def main():
    gold_path = OUT / 'original-working-reference.json'
    raw_path = OUT / 'baseline/predictions.jsonl'
    raw_digest = digest(raw_path)
    raw = [json.loads(line) for line in raw_path.read_text().splitlines() if line.strip()]
    gold = json.loads(gold_path.read_text())
    labels = {row['record_id']: row for row in gold['cases']}
    inputs = json.loads((OUT / 'inputs317.json').read_text())
    input_ids = [row['record_id'] for row in inputs]
    assert len(raw) == len(labels) == len(input_ids) == 317
    assert {row['record_id'] for row in raw} == set(input_ids) == set(labels)
    assert len({row['record_id'] for row in raw}) == len(raw)
    captured = {row['record_id']: row for row in raw}
    batches = {}
    semantic = {}
    for number in range(1, 6):
        path = WORK / f'baseline-review-{number}.json'
        batches[path.name] = digest(path)
        for decision in json.loads(path.read_text()):
            assert decision['record_id'] not in semantic
            semantic[decision['record_id']] = decision
    need = {rid for rid, row in captured.items() if row['questions'] and labels[rid]['questions']}
    assert need == set(semantic), (need - set(semantic), set(semantic) - need)
    projection, decisions = [], []
    for rid in input_ids:
        row, expected = captured[rid], labels[rid]
        qs, targets = row['questions'], expected['questions']
        if rid in semantic:
            reviewed = semantic[rid]
            assert reviewed['questions_sha256'] == value_hash(qs), rid
            assert reviewed['gold_sha256'] == value_hash(targets), rid
            whole, facts, reason = reviewed['whole'], reviewed['facts'], reviewed['reason']
            origin = 'assistant_semantic_review'
        else:
            assert not qs or not targets
            whole, facts = [], []
            reason = 'No possible match because the gold or predicted question list is empty.'
            origin = 'deterministic_empty_side'
        projection.append({'record_id': rid, 'group': row['group'], 'fold': row['fold'],
                           'bucket': expected['bucket'], 'questions': {'baseline': qs}})
        decisions.append({'record_id': rid, 'questions_sha256': value_hash(qs), 'gold_sha256': value_hash(targets),
                          'methods': {'baseline': {'whole': whole, 'facts': facts}},
                          'review_origin': origin, 'reason': reason})
    projection_path = OUT / 'baseline-score-predictions.jsonl'
    projection_path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in projection))
    bound = bind_review(projection_path, gold_path, decisions,
                        reviewer='Assistant semantic review batches 1–5; deterministic zero matches for empty-side cases')
    bound['review_kind'] = 'Assistant semantic review, not independent human acceptance.'
    bound['source_full_predictions_sha256'] = raw_digest
    bound['review_batches_sha256'] = batches
    bound['scope'] = 'All 317 fixed working-eval cases; retrospective grouped folds; frozen and holdout excluded.'
    review_path = OUT / 'baseline-bound-review.json'
    write(review_path, bound)
    overall = score_bound_review(projection_path, gold_path, bound)['baseline']
    by_bucket, by_fold = {}, {}
    for dimension, destination in [('bucket', by_bucket), ('fold', by_fold)]:
        for value in sorted({row[dimension] for row in projection}):
            rows = [row for row in projection if row[dimension] == value]
            ids = {row['record_id'] for row in rows}
            metrics = score_subset(rows, [labels[rid] for rid in input_ids if rid in ids],
                                   [review for review in decisions if review['record_id'] in ids])
            destination[str(value)] = {'cases': len(rows), 'groups': len({row['group'] for row in rows}), **metrics}
    assert digest(raw_path) == raw_digest
    report = {'method': 'baseline', 'cases': 317, 'groups': len({row['group'] for row in projection}),
              'gold_positive_cases': sum(bool(row['questions']) for row in labels.values()),
              'predicted_positive_cases': sum(bool(row['questions']) for row in raw),
              'gold_empty_cases_with_questions': sum(bool(row['questions']) and not labels[row['record_id']]['questions'] for row in raw),
              'manual_semantic_cases': len(semantic), 'deterministic_empty_side_cases': 317 - len(semantic),
              'overall': overall, 'by_bucket': by_bucket, 'by_fold': by_fold,
              'fold_interpretation': 'Retrospective robustness on the existing grouped working folds, not unseen validation.',
              'review_kind': bound['review_kind'], 'frozen_cases': 0, 'holdout_cases': 0,
              'source_full_predictions_sha256': raw_digest, 'score_predictions_sha256': digest(projection_path),
              'gold_sha256': digest(gold_path), 'bound_review_sha256': digest(review_path),
              'route_counts': dict(Counter(row['snapshot']['route'] for row in raw)),
              'schema_valid_cases': sum(not row['schema_errors'] for row in raw)}
    write(OUT / 'baseline-score.json', report)
    print(json.dumps({key: report[key] for key in ['cases', 'gold_positive_cases', 'predicted_positive_cases',
                      'gold_empty_cases_with_questions', 'manual_semantic_cases', 'overall']}, indent=2))


if __name__ == '__main__':
    main()
