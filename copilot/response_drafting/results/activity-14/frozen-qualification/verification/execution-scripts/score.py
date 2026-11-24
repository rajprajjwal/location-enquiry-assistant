"""Bind semantic frozen judgements to exact outputs and unchanged gold labels."""
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/activity14-frozen-qualification'
REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')
PRIOR = REPO / 'copilot/response_drafting/results/activity-14/frozen-locked'
manifest = json.loads((OUT / 'run-manifest.json').read_text())
sys.path.insert(0, manifest['runtime'])
from copilot.diagnostics.evaluation import bind_review, score_bound_review


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def question_digest(questions):
    return sha256(json.dumps(questions, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    predictions = OUT / 'predictions.jsonl'
    gold = OUT / 'locked-gold.json'
    assert digest(gold) == manifest['gold_sha256']
    assert digest(predictions) and digest(PRIOR / 'predictions.jsonl') == manifest['prior_predictions_sha256']
    rows = [json.loads(line) for line in predictions.read_text().splitlines()]
    assert [r['record_id'] for r in rows] == manifest['frozen_record_ids'] and len(rows) == 80
    labels = {r['record_id']: r['questions'] for r in load(gold)['cases']}
    old_predictions = {r['record_id']: r for r in
        (json.loads(line) for line in (PRIOR / 'predictions.jsonl').read_text().splitlines())}
    old_review = load(PRIOR / 'question-review.bound.json')
    assert old_review['predictions_sha256'] == manifest['prior_predictions_sha256']
    assert old_review['gold_sha256'] == manifest['gold_sha256']
    old = {r['record_id']: r['methods']['integrated'] for r in old_review['cases']}
    annotated = {}
    for name, assigned in [('question-review-first40.json', rows[:40]),
                            ('question-review-second40.json', rows[40:])]:
        data = load(OUT / name)
        assert data['source_gold_sha256'] == manifest['gold_sha256']
        assert [r['record_id'] for r in data['cases']] == [r['record_id'] for r in assigned]
        for case, actual in zip(data['cases'], assigned, strict=True):
            assert case['questions_sha256'] == question_digest(actual['questions']['integrated'])
            assert case['record_id'] not in annotated
            annotated[case['record_id']] = case
    bound_cases = []
    for row in rows:
        rid = row['record_id']
        assert row['gold'] == labels[rid]
        assert row['questions']['baseline'] == old_predictions[rid]['questions']['integrated']
        current = annotated[rid]
        bound_cases.append({'record_id': rid, 'methods': {
            'baseline': old[rid],
            'integrated': {key: current[key] for key in ['whole', 'facts', 'notes']}}})
    review = bind_review(predictions, gold, bound_cases,
        reviewer='Assistant semantic review with independent cross-checks against unchanged frozen questions and prior atomic facts; historical baseline judgements preserved. Not independent human acceptance.')
    metrics = score_bound_review(predictions, gold, review)
    write(OUT / 'question-review.bound.json', review)
    write(OUT / 'scores.json', metrics)

    analysis = []
    for row in rows:
        rid = row['record_id']
        judgement = annotated[rid]
        covered = {(g, f) for _, g, f in judgement['facts']}
        whole = {g for _, g in judgement['whole']}
        matched_predictions = {p for p, _ in judgement['whole']}
        partial_predictions = {p for p, _, _ in judgement['facts']} - matched_predictions
        missed = [{'question': g, 'fact': f, 'text': text}
                  for g, question in enumerate(labels[rid], 1)
                  for f, text in enumerate(question['facts'], 1) if (g, f) not in covered]
        complete_without_whole = [g for g, question in enumerate(labels[rid], 1)
                                 if g not in whole and all((g, f) in covered for f in range(1, len(question['facts']) + 1))]
        analysis.append({'record_id': rid, 'bucket': row['bucket'], 'query': row['query'],
            'gold_questions': labels[rid], 'actual_questions': row['questions']['integrated'],
            'whole_matches': judgement['whole'], 'partial_fact_matches': judgement['facts'],
            'missed_facts': missed, 'gold_groups_fully_covered_without_whole_match': complete_without_whole,
            'predictions_with_partial_but_no_whole_match': sorted(partial_predictions),
            'notes': judgement['notes']})
    write(OUT / 'per-case-question-analysis.json', analysis)
    diagnostics = {
        'gold_positive_cases': sum(bool(labels[r['record_id']]) for r in rows),
        'empty_gold_cases': sum(not labels[r['record_id']] for r in rows),
        'gold_positive_cases_without_questions': sum(bool(labels[r['record_id']]) and not r['questions']['integrated'] for r in rows),
        'empty_gold_cases_with_questions': sum(not labels[r['record_id']] and bool(r['questions']['integrated']) for r in rows),
        'question_groups_fully_fact_covered_without_whole_match': sum(len(r['gold_groups_fully_covered_without_whole_match']) for r in analysis),
        'matched_case_ids': [r['record_id'] for r in analysis if r['whole_matches']],
        'covered_fact_case_ids': [r['record_id'] for r in analysis if r['partial_fact_matches']],
        'semantic_review': 'Actual text and required meaning/granularity; no field-name-only credit; no label changes.',
        'independent_human_review': False,
    }
    write(OUT / 'question-diagnostics.json', diagnostics)
    print(json.dumps({'scores': metrics, 'diagnostics': diagnostics}, indent=2))


if __name__ == '__main__':
    main()
