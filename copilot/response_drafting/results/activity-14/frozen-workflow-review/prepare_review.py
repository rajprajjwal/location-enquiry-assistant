"""Prepare immutable question-review batches from captured frozen predictions."""
from hashlib import sha256
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def value_hash(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write_once(path, value):
    text = json.dumps(value, indent=2, ensure_ascii=False) + '\n'
    if path.exists() and path.read_text() != text:
        raise ValueError('A prepared review batch must not change: ' + path.name)
    path.write_text(text)


def main():
    gold = json.loads((OUT / 'locked-gold.json').read_text())['cases']
    complete_lines = (OUT / 'predictions.jsonl').read_text().split('\n')[:-1]
    rows = [json.loads(line) for line in complete_lines if line]
    assert [row['record_id'] for row in rows] == [row['record_id'] for row in gold[:len(rows)]]
    for start in range(0, len(rows) - 19, 20):
        packet = []
        for row, label in zip(rows[start:start + 20], gold[start:start + 20]):
            questions = row['questions']['updated']
            packet.append({'record_id': row['record_id'], 'bucket': label['bucket'],
                'query': row['query'], 'history': row['history'], 'questions': questions,
                'gold': label['questions'], 'requires_semantic_review': bool(questions and label['questions']),
                'questions_sha256': value_hash(questions), 'gold_sha256': value_hash(label['questions']),
                'prediction_row_sha256': value_hash(row)})
        write_once(OUT / f'review-batch-{start // 20 + 1}.json', packet)
        print(json.dumps({'batch': start // 20 + 1, 'cases': len(packet),
                          'semantic_cases': sum(row['requires_semantic_review'] for row in packet)}))


if __name__ == '__main__':
    main()
