"""Reuse exact working-question judgements and isolate changed positive candidates."""
import hashlib
import json
from pathlib import Path

REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')
OUT = REPO / 'copilot/response_drafting/results/activity-14/workflow-review'
WORK = Path(__file__).resolve().parent


def value_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    gold_path, base_path, candidate_path = (OUT / 'original-working-reference.json',
                                          OUT / 'baseline/predictions.jsonl', OUT / 'candidate/predictions.jsonl')
    labels = {row['record_id']: row for row in json.loads(gold_path.read_text())['cases']}
    baseline = {row['record_id']: row for row in map(json.loads, base_path.read_text().splitlines())}
    candidate = list(map(json.loads, candidate_path.read_text().splitlines()))
    bound_path = OUT / 'baseline-bound-review.json'
    bound = json.loads(bound_path.read_text())
    assert bound['source_full_predictions_sha256'] == digest(base_path)
    assert bound['gold_sha256'] == digest(gold_path)
    original = {row['record_id']: row for row in bound['cases']}
    assert len(candidate) == len(baseline) == len(labels) == 317
    assert {row['record_id'] for row in candidate} == set(baseline) == set(labels)
    reused, fresh = [], []
    counts = {'empty_side': 0, 'identical_questions': 0, 'reordered_identical_questions': 0, 'fresh_semantic_review': 0}
    for row in candidate:
        rid = row['record_id']
        old, new, gold = baseline[rid]['questions'], row['questions'], labels[rid]['questions']
        assert row['query'] == baseline[rid]['query'] and row['history'] == baseline[rid]['history'], rid
        prior = original[rid]
        assert prior['questions_sha256'] == value_hash(old) and prior['gold_sha256'] == value_hash(gold)
        known = prior['methods']['baseline']
        if not new or not gold:
            kind, whole, facts = 'empty_side', [], []
            reason = 'No possible match because the predicted or gold question list is empty.'
        elif new == old:
            kind, whole, facts = 'identical_questions', known['whole'], known['facts']
            reason = 'Reused the baseline semantic judgement for identical questions and unchanged enquiry/history/reference.'
        elif len(old) == len(new) == len(set(old)) and set(old) == set(new):
            kind = 'reordered_identical_questions'
            permutation = {index: new.index(text) + 1 for index, text in enumerate(old, 1)}
            whole = [[permutation[p], g] for p, g in known['whole']]
            facts = [[permutation[p], g, f] for p, g, f in known['facts']]
            reason = 'Reused baseline semantic judgements by exact unique question text, remapping prediction indices after reordering.'
        else:
            counts['fresh_semantic_review'] += 1
            fresh.append({'record_id': rid, 'query': row['query'], 'history': row['history'],
                          'questions': new, 'gold': gold,
                          'questions_sha256': value_hash(new), 'gold_sha256': value_hash(gold)})
            continue
        counts[kind] += 1
        reused.append({'record_id': rid, 'questions_sha256': value_hash(new), 'gold_sha256': value_hash(gold),
                       'whole': whole, 'facts': facts, 'reason': reason, 'review_origin': kind})
    assert len(reused) + len(fresh) == 317
    write(OUT / 'candidate-reused-judgements.json', reused)
    write(OUT / 'candidate-review-pending.json', fresh)
    batch_paths = []
    for start in range(0, len(fresh), 7):
        path = WORK / f'candidate-review-batch-{start // 7 + 1}.json'
        text = json.dumps(fresh[start:start + 7], indent=2, ensure_ascii=False) + '\n'
        if path.exists() and path.read_text() != text:
            raise ValueError(f'Review packet changed: {path.name}')
        path.write_text(text)
        batch_paths.append({'path': str(path), 'cases': len(fresh[start:start + 7]), 'sha256': digest(path)})
    report = {'cases': 317, 'counts': counts, 'review_batches': batch_paths,
              'candidate_predictions_sha256': digest(candidate_path), 'baseline_predictions_sha256': digest(base_path),
              'gold_sha256': digest(gold_path), 'baseline_bound_review_sha256': digest(bound_path),
              'review_policy': 'Reuse only exact text with unchanged enquiry/history and gold; remap unique question order. Changed positive nonempty questions require fresh semantic review.',
              'frozen_cases': 0, 'holdout_cases': 0,
              'fresh_semantic_review_complete': not fresh}
    write(OUT / 'candidate-review-preparation.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
