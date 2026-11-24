"""Read only the fixed working-eval IDs and lock unchanged workbook question text."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')
OUT = Path(__file__).resolve().parent
BOARD = ROOT / 'work/activity-10-working-eval/working-cases.json'
BOOK = REPO / 'data/ground-truth.xlsx'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once(name, value):
    path = OUT / name
    text = json.dumps(value, indent=2, ensure_ascii=False) + '\n'
    if path.exists() and path.read_text() != text:
        raise ValueError(f'Refusing to overwrite a different locked file: {name}')
    path.write_text(text)


def main():
    board = json.loads(BOARD.read_text())
    ordered = board['cases']
    allowed = {row['id']: row for row in ordered}
    assert len(ordered) == len(allowed) == 317
    before_hash = digest(BOOK)
    # Use the existing adapter's exact turn parser without loading app dependencies.
    adapter = REPO / 'copilot/enquiry_interpretation/gt_adapter.py'
    tree = ast.parse(adapter.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'from_gt_question')
    namespace = {'re': re, 'TURN_MARKER': re.compile(r'^\s*\[(user|assistant)\]\s*', re.I)}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(adapter), 'exec'), namespace)
    from_gt_question = namespace['from_gt_question']
    selected = {}
    book = load_workbook(BOOK, read_only=True, data_only=True)
    try:
        iterator = book['Data'].values
        header = next(iterator)
        used_columns = ['id', 'question', 'split', 'frozen_core', 'gold_clarifying_questions', 'api', 'intent', 'sub_intent', 'primary_team']
        assert all(header.count(name) == 1 for name in used_columns)
        col = {name: header.index(name) for name in used_columns}
        for values in iterator:
            rid = values[col['id']]
            if rid not in allowed:
                continue
            assert rid not in selected
            assert values[col['split']] == 'eval' and values[col['frozen_core']] is False
            # Query and label cells are accessed only after the allowlist check.
            row = {name: values[index] for name, index in col.items()}
            assert row['question'] == allowed[rid]['question']
            selected[rid] = row
    finally:
        book.close()
    assert set(selected) == set(allowed)
    inputs, references = [], []
    counts, positives, question_counts = Counter(), Counter(), Counter()
    for case in ordered:
        rid = case['id']
        row = selected[rid]
        query, history = from_gt_question(row['question'])
        raw = row['gold_clarifying_questions'] or ''
        assert isinstance(raw, str)
        stripped = raw.strip()
        questions = list(dict.fromkeys(re.findall(r'(?m)^\s*[-•]\s+(.+)$', stripped) or ([stripped] if stripped else [])))
        inputs.append({'record_id': rid, 'query': query, 'history': history, 'known_facts': [],
                       'bucket': case['bucket'], 'group': case['group'], 'fold': case['fold']})
        references.append({'record_id': rid, 'bucket': case['bucket'], 'group': case['group'], 'fold': case['fold'],
                           'api': row['api'], 'intent': row['intent'], 'sub_intent': row['sub_intent'], 'team': row['primary_team'],
                           'original_question': row['question'], 'gold_clarifying_questions_raw': raw,
                           'questions': [{'question': question} for question in questions]})
        counts[case['bucket']] += 1
        positives[case['bucket']] += bool(questions)
        question_counts[case['bucket']] += len(questions)
    assert digest(BOOK) == before_hash
    write_once('inputs317.json', inputs)
    write_once('original-working-reference.json', {
        'status': 'original_gt_question_text_locked_atomic_decomposition_pending',
        'reference_policy': 'Original workbook questions unchanged. No supplied-fact contradiction or materiality correction is applied to this primary reference.',
        'question_normalization': 'Strip list bullets and outer whitespace; deduplicate identical question text, matching the established working-reference preparation.',
        'source_workbook_sha256': before_hash, 'working_allowlist_sha256': digest(BOARD),
        'cases': references,
    })
    manifest = {'cases': len(inputs), 'groups': len({row['group'] for row in inputs}),
                'positive_cases': sum(positives.values()), 'gold_question_groups': sum(question_counts.values()),
                'empty_gold_cases': len(inputs) - sum(positives.values()),
                'frozen_cases': 0, 'holdout_cases': 0,
                'source_workbook_sha256': before_hash, 'working_allowlist_sha256': digest(BOARD),
                'adapter_sha256': digest(adapter), 'columns_zero_based': col,
                'inputs_sha256': digest(OUT / 'inputs317.json'),
                'reference_sha256': digest(OUT / 'original-working-reference.json'),
                'by_bucket': {key: {'cases': counts[key], 'positive_cases': positives[key],
                                     'questions': question_counts[key]} for key in sorted(counts)}}
    write_once('original-reference-manifest.json', manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
