"""Bind independently checked frozen question judgements and reproduce metrics."""
from hashlib import sha256
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT / 'runtime'))
from copilot.diagnostics.evaluation import bind_review, score_bound_review


def value_hash(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def reviewed_cases(path, batch):
    value = json.loads(path.read_text())
    if isinstance(value, dict):
        packet = OUT / f'review-batch-{batch}.json'
        assert value['source_batch_sha256'] == sha256(packet.read_bytes()).hexdigest()
        value = value['cases']
    assert isinstance(value, list) and len(value) == 20
    return value


def main():
    predictions, gold_path = OUT / 'predictions.jsonl', OUT / 'locked-gold.json'
    rows = [json.loads(line) for line in predictions.read_text().splitlines()]
    gold = json.loads(gold_path.read_text())['cases']
    assert len(rows) == len(gold) == 80
    assert [row['record_id'] for row in rows] == [row['record_id'] for row in gold]
    primary, independent = [], []
    for batch in range(1, 5):
        primary.extend(reviewed_cases(OUT / f'primary-review-{batch}.json', batch))
        independent.extend(reviewed_cases(OUT / f'independent-review-{batch}.json', batch))
    p = {row['record_id']: row for row in primary}
    q = {row['record_id']: row for row in independent}
    assert len(p) == len(primary) == len(q) == len(independent) == 80
    resolutions_path = OUT / 'review-resolutions.json'
    resolutions = json.loads(resolutions_path.read_text()) if resolutions_path.exists() else {}
    decisions, disagreements = [], []
    for row, label in zip(rows, gold):
        rid = row['record_id']
        for review in (p[rid], q[rid]):
            assert review['questions_sha256'] == value_hash(row['questions']['updated'])
            assert review['gold_sha256'] == value_hash(label['questions'])
            assert review['prediction_row_sha256'] == value_hash(row)
        first = {key: sorted(p[rid][key]) for key in ('whole', 'facts')}
        second = {key: sorted(q[rid][key]) for key in ('whole', 'facts')}
        if first != second:
            disagreements.append({'record_id': rid, 'primary': first, 'independent': second})
            resolution = resolutions.get(rid)
            if not resolution:
                continue
            assert resolution['questions_sha256'] == value_hash(row['questions']['updated'])
            assert resolution['gold_sha256'] == value_hash(label['questions'])
            assert resolution['reason'].strip()
            first = {key: resolution[key] for key in ('whole', 'facts')}
        decisions.append({'record_id': rid, 'methods': {'updated': first}})
    write(OUT / 'review-crosscheck.json', {'cases': 80, 'disagreements': disagreements,
          'resolved': sum(item['record_id'] in resolutions for item in disagreements),
          'reviewer_type': 'Two assistant semantic reviews; not independent human acceptance.'})
    if len(decisions) != 80:
        raise ValueError('Resolve and document every semantic-review disagreement before scoring.')
    review = bind_review(predictions, gold_path, decisions,
                         reviewer='Assistant semantic review with independent assistant cross-check')
    score = score_bound_review(predictions, gold_path, review)
    write(OUT / 'question-review.bound.json', review)
    write(OUT / 'scores.json', score)
    print(json.dumps(score, indent=2))


if __name__ == '__main__':
    main()
