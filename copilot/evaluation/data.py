"""Read current gold without passing references to either generation arm."""
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path

from openpyxl import load_workbook
from copilot.paths import REPO_ROOT
from copilot.enquiry_interpretation.gt_adapter import from_gt_question
from copilot.validation.rules import normalize_enum
from mapping.map_gt import map_record, load_vocab

WORKBOOK = REPO_ROOT / 'data/ground-truth.xlsx'
FROZEN = REPO_ROOT / 'eval/frozen-interpretation'
WORKING = REPO_ROOT / 'copilot/response_drafting/results/activity-14/workflow-review/original-working-reference.json'


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def memberships():
    frozen = set(json.loads((FROZEN/'manifest.json').read_text())['frozen_record_ids'])
    working = {r['record_id']: r for r in json.loads(WORKING.read_text())['cases']}
    if len(frozen) != 80 or len(working) != 317 or frozen & working.keys():
        raise ValueError('Unexpected approved split membership')
    return frozen, working


def read_cases(split='working_eval'):
    if split not in {'working_eval', 'frozen', 'holdout'}:
        raise ValueError('Unknown evaluation split')
    frozen, working = memberships()
    pinned = {}
    if split=='frozen':
        manifest=json.loads((FROZEN/'manifest.json').read_text())
        if file_hash(FROZEN/'inputs.jsonl')!=manifest['inputs_sha256']:
            raise ValueError('Pinned frozen inputs changed')
        pinned={r['record_id']:r for r in map(json.loads,(FROZEN/'inputs.jsonl').read_text().splitlines())}
    vocab = load_vocab()
    book = load_workbook(WORKBOOK, read_only=True, data_only=True)
    cases = []
    try:
        values = book['Data'].iter_rows(values_only=True)
        headers = next(values)
        for values_row in values:
            row = dict(zip(headers, values_row))
            identifier = row['id']
            selected = (identifier in working if split == 'working_eval' else
                        identifier in frozen if split == 'frozen' else row['split'] == 'holdout')
            if not selected:
                continue
            if (split != 'holdout' and row['split'] != 'eval') or (split == 'working_eval' and row['frozen_core']):
                raise ValueError('Split labels disagree with approved membership')
            query, history = from_gt_question(row['question'])
            context = {'query':query, 'history':history, 'known_facts':[]}
            if split == 'frozen':
                expected = {k:pinned[identifier][k] for k in context}
                if context != expected:
                    raise ValueError(f'Frozen input differs from pinned export: {identifier}')
            mapped, issues = map_record(row, vocab, None)
            cases.append({'record_id':identifier, 'split':split, 'bucket':row['bucket'],
                          'api':normalize_enum('api',row['api']), 'team':row['primary_team'],
                          'group':working.get(identifier,{}).get('group',row['template_family']),
                          'input':context, 'gold':mapped, 'mapping_issues':issues, 'rubric':row['rubric'],
                          'reference_context':row['context'], 'review_status':row['review_status']})
    finally:
        book.close()
    if len({r['record_id'] for r in cases}) != len(cases):
        raise ValueError('Duplicate gold identifiers')
    expected = 317 if split == 'working_eval' else 80 if split == 'frozen' else len(cases)
    if len(cases) != expected:
        raise ValueError('Missing approved cases')
    return sorted(cases, key=lambda r:r['record_id'])


def sample(cases, per_bucket=1, exclude_groups=()):
    selected, groups, counts = [], set(exclude_groups), Counter()
    for _ in range(per_bucket):
        for bucket in sorted({r['bucket'] for r in cases}):
            options = [r for r in cases if r['bucket']==bucket and r['group'] not in groups]
            if not options:
                raise ValueError(f'Not enough independent groups in {bucket}')
            row = min(options, key=lambda r:(counts[r['api']],r['record_id']))
            selected.append(row)
            groups.add(row['group'])
            counts[row['api']] += 1
    return selected
