"""Verify the unchanged frozen inputs and question reference before execution."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from openpyxl import load_workbook

REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')
SOURCE = REPO / 'copilot/response_drafting/results/activity-14/frozen-qualification'
OLD = REPO / 'copilot/response_drafting/results/activity-14/frozen-locked'
OUT = Path(__file__).resolve().parent
EXPECTED_INPUTS = 'b8c26d867bca77364d7348957b22ea8b7cda85b7d918f7cefd398f8b1ad39d81'
EXPECTED_GOLD = '7c5c44fb2f1d216957585b7edaf765406b791da2c13decd6c05cd0e4d63000fb'
EXPECTED_QUESTIONS = 'b5f8fce68f5d751931f74403671bc402dc624bb2df73f167a2a2ecd782518984'
EXPECTED_WORKBOOK = '13c9018a7ecec44bc240e4c1f884aaf31965b55280050250c2cb59c967253d68'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    workbook_path = REPO / 'data/ground-truth.xlsx'
    workbook_before = digest(workbook_path)
    assert workbook_before == EXPECTED_WORKBOOK
    inputs_path, gold_path, questions_path = SOURCE / 'inputs.jsonl', SOURCE / 'locked-gold.json', SOURCE / 'frozen-questions.json'
    assert digest(inputs_path) == EXPECTED_INPUTS
    assert digest(gold_path) == digest(OLD / 'locked-gold.json') == EXPECTED_GOLD
    assert digest(questions_path) == digest(OLD / 'frozen-questions.json') == EXPECTED_QUESTIONS
    inputs = list(map(json.loads, inputs_path.read_text().splitlines()))
    gold, official, packet = read(gold_path), read(questions_path), read(SOURCE / 'review-cases.json')
    input_ids = [r['record_id'] for r in inputs]
    assert len(input_ids) == len(set(input_ids)) == 80
    assert all([r['record_id'] for r in rows] == input_ids for rows in [gold['cases'], official['cases'], packet])
    assert all(a['query'] == b['query'] and a.get('history', []) == b.get('history', []) for a, b in zip(inputs, packet, strict=True))
    assert sum(len(r['questions']) for r in gold['cases']) == 75
    assert sum(len(q['facts']) for r in gold['cases'] for q in r['questions']) == 99
    assert all([q['question'] for q in a['questions']] == [q['question'] for q in b['questions']]
               for a, b in zip(gold['cases'], official['cases'], strict=True))
    gold_by_id = {r['record_id']: r for r in gold['cases']}
    input_by_id = {r['record_id']: r for r in inputs}
    adapter_path = REPO / 'copilot/enquiry_interpretation/gt_adapter.py'
    adapter_tree = ast.parse(adapter_path.read_text())
    function = next(node for node in adapter_tree.body if isinstance(node, ast.FunctionDef) and node.name == 'from_gt_question')
    namespace = {'re': re, 'TURN_MARKER': re.compile(r'^\s*\[(user|assistant)\]\s*', re.I)}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(adapter_path), 'exec'), namespace)
    split = namespace['from_gt_question']
    matched, api_counts = [], Counter()
    book = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        rows = book['Data'].values
        header = next(rows)
        columns = {name: header.index(name) for name in ['id', 'question', 'gold_clarifying_questions', 'split', 'frozen_core', 'api']}
        for values in rows:
            rid = values[columns['id']]
            if rid not in input_by_id:
                continue
            # No holdout question or label cell is accessed.
            assert values[columns['split']] == 'eval' and values[columns['frozen_core']] is True
            query, history = split(values[columns['question']])
            assert query == input_by_id[rid]['query'] and history == input_by_id[rid].get('history', []), rid
            raw = (values[columns['gold_clarifying_questions']] or '').strip()
            questions = list(dict.fromkeys(re.findall(r'(?m)^\s*[-•]\s+(.+)$', raw) or ([raw] if raw else [])))
            assert questions == [q['question'] for q in gold_by_id[rid]['questions']], rid
            api_counts[values[columns['api']]] += 1
            matched.append(rid)
    finally:
        book.close()
    assert set(matched) == set(input_ids) and len(matched) == 80
    assert digest(workbook_path) == workbook_before
    assert set(api_counts.values()) == {20} and len(api_counts) == 4
    manifest = read(SOURCE / 'run-manifest.json')
    scores = read(SOURCE / 'scores.json')
    verification = {
        'passed': True, 'records': 80, 'unique_ids': 80, 'same_order_across_inputs_and_references': True,
        'frozen_records': 80, 'holdout_records': 0, 'by_api': dict(api_counts),
        'original_question_groups': 75, 'original_atomic_facts': 99,
        'gold_positive_cases': sum(bool(r['questions']) for r in gold['cases']),
        'gold_empty_cases': sum(not r['questions'] for r in gold['cases']),
        'workbook_exact_queries_history_and_question_lists': 80,
        'normalization_drift': False, 'workbook_changed': False,
        'source_hashes': {str(p.relative_to(REPO)): digest(p) for p in [inputs_path, gold_path, questions_path,
                          SOURCE / 'ground-truth-frozen.csv', SOURCE / 'review-cases.json', SOURCE / 'question-review.bound.json',
                          SOURCE / 'scores.json', SOURCE / 'run-manifest.json', workbook_path]},
        'previous_latest_metrics': scores['integrated'], 'previous_older_metrics': read(OLD / 'scores.json')['integrated'],
        'previous_retrieval': manifest['retrieval'], 'previous_few_shot_interpretation': manifest['few_shot_interpretation'],
        'review_provenance': read(SOURCE / 'question-review.bound.json')['reviewer'],
        'comparability': 'Use these exact 75 original question groups and 99 prior atomic facts. The working-eval 164-fact decomposition is a different cohort and must not replace this reference.',
        'source_or_gold_changes': False,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    destination = OUT / 'frozen-reference-preflight.json'
    destination.write_text(json.dumps(verification, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({key: verification[key] for key in ['passed', 'records', 'original_question_groups', 'original_atomic_facts',
                      'workbook_exact_queries_history_and_question_lists', 'by_api', 'normalization_drift']}, indent=2))


if __name__ == '__main__':
    main()
