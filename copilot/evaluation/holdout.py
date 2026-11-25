"""Fail closed on unreviewed gold, unresolved leakage or a second final run."""
import csv
import json
from pathlib import Path
from copilot.paths import REPO_ROOT
from .data import WORKBOOK,file_hash

DUPLICATES=REPO_ROOT/'data/activity-5-duplicate-review.csv'
APPROVED_EXCLUSION='GT-LBS-DIR-010'


def split_pairs():
    with DUPLICATES.open(encoding='utf-8-sig') as stream:
        return [r for r in csv.DictReader(stream) if r['category']=='cross_split']


def approval_template(cases,output):
    value={'workbook_sha256':file_hash(WORKBOOK),'leakage_audit_sha256':file_hash(DUPLICATES),
           'reviewer':'','approved':False,'case_ids':[c['record_id'] for c in cases],
           'scope':'Review reference answers, source spans, rubrics and every flagged split pair before scored holdout.',
           'duplicate_dispositions':[{'record_a':r['record_a'],'record_b':r['record_b'],
               'decision':'exclude_holdout' if APPROVED_EXCLUSION in (r['record_a'],r['record_b']) else 'pending',
               'reason':r['review_note'] if APPROVED_EXCLUSION in (r['record_a'],r['record_b']) else ''} for r in split_pairs()]}
    Path(output).write_text(json.dumps(value,indent=2)+'\n')
    return value


def reserve(cases,approval,selection,ledger,output):
    reviewed=json.loads(Path(approval).read_text())
    selected=json.loads(Path(selection).read_text())
    expected={c['record_id'] for c in cases}
    if (not reviewed.get('approved') or not reviewed.get('reviewer') or
        reviewed.get('workbook_sha256')!=file_hash(WORKBOOK) or set(reviewed.get('case_ids',[]))!=expected or
        reviewed.get('leakage_audit_sha256')!=file_hash(DUPLICATES)):
        raise ValueError('Holdout requires a complete, hash-bound gold and leakage review')
    decisions={(r['record_a'],r['record_b']):r for r in reviewed.get('duplicate_dispositions',[])}
    excluded={APPROVED_EXCLUSION}
    for pair in split_pairs():
        decision=decisions.get((pair['record_a'],pair['record_b']),{})
        if decision.get('decision') not in {'exclude_holdout','distinct'} or not decision.get('reason'):
            raise ValueError('Every flagged eval–holdout pair needs a reasoned review decision')
        if decision['decision']=='exclude_holdout':
            excluded.add(pair['record_a'] if pair['split_a']=='holdout' else pair['record_b'])
    if not selected.get('locked') or not selected.get('repeatability_passed') or not selected.get('fresh_judge_repeatability_passed'):
        raise ValueError('Lock the working-eval winner and repeatability checks before holdout')
    binding={'workbook_sha256':file_hash(WORKBOOK),'selection_sha256':file_hash(selection),
             'review_sha256':file_hash(approval),'case_ids':sorted(expected-excluded),'output':str(Path(output).resolve())}
    ledger=Path(ledger)
    ledger.parent.mkdir(parents=True,exist_ok=True)
    if ledger.exists():
        previous=json.loads(ledger.read_text())
        if previous.get('binding')!=binding:
            raise ValueError('Holdout has already been reserved for another run')
    else:
        # Exclusive creation prevents concurrent final runs from claiming the set.
        with ledger.open('x') as stream:
            json.dump({'binding':binding,'state':'reserved'},stream,indent=2)
    return [c for c in cases if c['record_id'] in expected-excluded]
