"""Prepare or score a fixed working trial using exact, bound semantic judgements."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')
OUT = REPO / 'copilot/response_drafting/results/activity-14/workflow-review'
WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
from copilot.diagnostics.evaluation import bind_review, score_bound_review


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vh(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def load_trial(variant):
    path = OUT / variant / 'predictions.jsonl'
    rows = list(map(json.loads, path.read_text().splitlines()))
    assert len(rows) == len({r['record_id'] for r in rows}) == 317
    return path, rows


def prepare(args):
    gold_path = OUT / 'original-working-reference.json'
    labels = {r['record_id']: r for r in read(gold_path)['cases']}
    previous_path, old_rows = load_trial(args.previous)
    current_path, rows = load_trial(args.variant)
    previous = {r['record_id']: r for r in old_rows}
    bound_path = OUT / f'{args.previous}-bound-review.json'
    bound = read(bound_path)
    assert bound['gold_sha256'] == digest(gold_path)
    assert bound['source_full_predictions_sha256'] == digest(previous_path)
    prior = {r['record_id']: r for r in bound['cases']}
    assert set(labels) == set(previous) == set(prior) == {r['record_id'] for r in rows}
    equivalences = {}
    if args.equivalence_review:
        approved = read(args.equivalence_review)
        assert approved['previous_predictions_sha256'] == digest(previous_path)
        assert approved['current_predictions_sha256'] == digest(current_path)
        assert approved['gold_sha256'] == digest(gold_path)
        equivalences = {r['record_id']: r for r in approved['cases']}
    reused, pending, counts = [], [], Counter()
    for row in rows:
        rid = row['record_id']; before = previous[rid]; old = before['questions']; new = row['questions']; gold = labels[rid]['questions']
        assert row['query'] == before['query'] and row['history'] == before['history']
        source = prior[rid]
        assert source['questions_sha256'] == vh(old) and source['gold_sha256'] == vh(gold)
        methods = source['methods']; assert len(methods) == 1
        known = next(iter(methods.values()))
        mapping = None
        if not new or not gold:
            origin, whole, facts = 'empty_side', [], []
        elif new == old:
            origin, whole, facts = 'identical_questions', known['whole'], known['facts']
        elif len(new) == len(old) == len(set(new)) and set(new) == set(old):
            origin = 'reordered_identical_questions'
            mapping = {p: new.index(text) + 1 for p, text in enumerate(old, 1)}
        elif rid in equivalences:
            approved = equivalences[rid]
            assert approved['old_questions_sha256'] == vh(old) and approved['new_questions_sha256'] == vh(new)
            assert approved['context_sha256'] == vh({'query': row['query'], 'history': row['history']})
            assert approved['gold_sha256'] == vh(gold)
            mapping = {int(p): int(q) for p, q in approved['old_to_new_prediction_indices'].items()}
            assert set(mapping) == set(range(1, len(old) + 1)) and set(mapping.values()) == set(range(1, len(new) + 1))
            origin = 'context_reviewed_wording_equivalence'
        else:
            counts['fresh_semantic_review'] += 1
            pending.append({'record_id': rid, 'query': row['query'], 'history': row['history'], 'questions': new,
                            'gold': gold, 'questions_sha256': vh(new), 'gold_sha256': vh(gold)})
            continue
        if mapping:
            whole = [[mapping[p], g] for p, g in known['whole']]
            facts = [[mapping[p], g, f] for p, g, f in known['facts']]
        counts[origin] += 1
        reused.append({'record_id': rid, 'questions_sha256': vh(new), 'gold_sha256': vh(gold),
                       'whole': whole, 'facts': facts, 'review_origin': origin,
                       'reason': f'Reused bound {args.previous} judgements through {origin}; enquiry/history and primary gold unchanged.'})
    batches = []
    for start in range(0, len(pending), 7):
        path = WORK / f'{args.variant}-review-batch-{start // 7 + 1}.json'
        text = json.dumps(pending[start:start + 7], indent=2, ensure_ascii=False) + '\n'
        if path.exists() and path.read_text() != text:
            raise ValueError(f'Cannot overwrite a changed packet: {path}')
        path.write_text(text); batches.append({'path': str(path), 'cases': len(pending[start:start + 7]), 'sha256': digest(path)})
    write(OUT / f'{args.variant}-reused-judgements.json', reused)
    write(OUT / f'{args.variant}-review-pending.json', pending)
    report = {'variant': args.variant, 'previous': args.previous, 'cases': 317, 'counts': dict(counts), 'review_batches': batches,
              'source_predictions_sha256': digest(current_path), 'previous_predictions_sha256': digest(previous_path),
              'previous_bound_review_sha256': digest(bound_path), 'gold_sha256': digest(gold_path),
              'equivalence_review_sha256': digest(args.equivalence_review) if args.equivalence_review else None,
              'frozen_cases': 0, 'holdout_cases': 0}
    write(OUT / f'{args.variant}-review-preparation.json', report)
    print(json.dumps(report, indent=2))


def score_group(method, rows, labels, decisions):
    with TemporaryDirectory(prefix='trial-bound-score-') as tmp:
        p, g = Path(tmp) / 'pred.jsonl', Path(tmp) / 'gold.json'
        p.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)); write(g, {'cases': labels})
        bound = bind_review(p, g, decisions, reviewer='Assistant semantic judgements; subgroup reuse')
        return score_bound_review(p, g, bound)[method]


def score(args):
    prep = read(OUT / f'{args.variant}-review-preparation.json')
    assert prep['variant'] == args.variant
    raw_path, rows = load_trial(args.variant)
    gold_path = OUT / 'original-working-reference.json'
    assert prep['source_predictions_sha256'] == digest(raw_path) and prep['gold_sha256'] == digest(gold_path)
    labels = {r['record_id']: r for r in read(gold_path)['cases']}
    decisions = {r['record_id']: r for r in read(OUT / f'{args.variant}-reused-judgements.json')}
    review_sources = {}
    for path in args.reviews:
        review_sources[str(path)] = digest(path)
        for item in read(path):
            assert item['record_id'] not in decisions
            decisions[item['record_id']] = {**item, 'review_origin': 'fresh_assistant_semantic_review'}
    assert set(decisions) == set(labels) == {r['record_id'] for r in rows}
    projected, reviewed = [], []
    for row in rows:
        rid = row['record_id']; d = decisions[rid]
        assert d['questions_sha256'] == vh(row['questions']) and d['gold_sha256'] == vh(labels[rid]['questions'])
        projected.append({'record_id': rid, 'group': row['group'], 'fold': row['fold'], 'bucket': labels[rid]['bucket'],
                          'questions': {args.variant: row['questions']}})
        reviewed.append({**{key: d[key] for key in ['record_id', 'questions_sha256', 'gold_sha256', 'reason', 'review_origin']},
                         'methods': {args.variant: {'whole': d['whole'], 'facts': d['facts']}}})
    p = OUT / f'{args.variant}-score-predictions.jsonl'
    p.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in projected))
    bound = bind_review(p, gold_path, reviewed, reviewer='Assistant semantic review with exact/context-approved wording reuse')
    bound.update(source_full_predictions_sha256=digest(raw_path), review_sources_sha256=review_sources,
                 review_kind='Assistant semantic review, not independent human acceptance.',
                 scope='All317 fixed working-eval cases; retrospective grouped folds; frozen and holdout excluded.')
    review_path = OUT / f'{args.variant}-bound-review.json'; write(review_path, bound)
    overall = score_bound_review(p, gold_path, bound)[args.variant]
    by_bucket, by_fold = {}, {}
    for dim, destination in [('bucket', by_bucket), ('fold', by_fold)]:
        for value in sorted({r[dim] for r in projected}):
            subset = [r for r in projected if r[dim] == value]; ids = {r['record_id'] for r in subset}
            metrics = score_group(args.variant, subset, [labels[rid] for rid in ids], [r for r in reviewed if r['record_id'] in ids])
            destination[str(value)] = {'cases': len(subset), 'groups': len({r['group'] for r in subset}), **metrics}
    baseline = read(OUT / 'baseline-score.json')['overall']; previous = read(OUT / f'{prep["previous"]}-score.json')['overall']
    report = {'method': args.variant, 'cases': 317, 'overall': overall, 'baseline_overall': baseline, 'previous_overall': previous,
              'delta_from_baseline': {key: overall[key] - baseline[key] for key in ['f1', 'precision', 'recall', 'fact_recall', 'questions_on_empty_gold']},
              'delta_from_previous': {key: overall[key] - previous[key] for key in ['f1', 'precision', 'recall', 'fact_recall', 'questions_on_empty_gold']},
              'by_bucket': by_bucket, 'by_fold': by_fold,
              'gold_empty_cases_with_questions': sum(bool(r['questions']) and not labels[r['record_id']]['questions'] for r in rows),
              'route_counts': dict(Counter(r['snapshot']['route'] for r in rows)), 'schema_valid_cases': sum(not r['schema_errors'] for r in rows),
              'reference_policy': 'Original working GT unchanged; assistant-decomposed facts and semantic review. No independent human acceptance.',
              'fold_interpretation': 'Retrospective grouped working folds, not untouched validation.',
              'frozen_cases': 0, 'holdout_cases': 0, 'source_predictions_sha256': digest(raw_path),
              'gold_sha256': digest(gold_path), 'bound_review_sha256': digest(review_path)}
    write(OUT / f'{args.variant}-score.json', report)
    print(json.dumps({key: report[key] for key in ['method', 'cases', 'overall', 'delta_from_previous']}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'score'])
    parser.add_argument('--variant', required=True)
    parser.add_argument('--previous', default='candidate')
    parser.add_argument('--equivalence-review', type=Path)
    parser.add_argument('--reviews', type=Path, nargs='*', default=[])
    args = parser.parse_args()
    if not args.variant or Path(args.variant).name != args.variant:
        raise ValueError('Variant must be a local run-directory name.')
    prepare(args) if args.action == 'prepare' else score(args)


if __name__ == '__main__':
    main()
