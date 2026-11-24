"""Lock working inputs, original labels and separate reference corrections."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')
OUT = ROOT / 'outputs/fact-binding-working'
RUNTIME = ROOT / 'work/fact-binding/runtime'
SOURCE = ROOT / 'outputs/qualification-validation-working/full-36'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    def copy(src, dst):
        if Path(src).suffix == '.py' or Path(src).stat().st_size < 1000000:
            return shutil.copy2(src, dst)
        Path(dst).symlink_to(Path(src).resolve())
        return dst
    RUNTIME.mkdir(exist_ok=False)
    shutil.copytree(REPO / 'copilot', RUNTIME / 'copilot', copy_function=copy,
                    ignore=shutil.ignore_patterns('results', '__pycache__'))
    for path in REPO.iterdir():
        if path.name not in {'copilot', '.git', '.venv'}:
            (RUNTIME / path.name).symlink_to(path)
    for name in ['review-cases.json', 'locked-gold.json', 'original-working-labels.json']:
        shutil.copy2(SOURCE / name, OUT / name)
    original = json.loads((OUT / 'locked-gold.json').read_text())
    reviewed = json.loads(json.dumps(original))
    removed = {**{f'GT-LBS-AC-{i:03}': {'details_sku'} for i in range(21, 25)},
               'GT-LBS-RG-010': {'storage_required'}, 'GT-LBS-RG-014': {'storage_required'},
               'GT-LBS-DIR-050': {'traffic_required'}, 'GT-LBS-RG-228': {'languages'},
               'GT-LBS-RG-230': {'rooftop_hard_filter', 'address_elements_required'},
               'GT-LBS-DM-228': {'billing_basis'}}
    changes = []
    for row in reviewed['cases']:
        previous = json.loads(json.dumps(row['questions']))
        fields = removed.get(row['record_id'], set())
        row['questions'] = [q for q in row['questions'] if not set(q['facts']) <= fields]
        if row['record_id'] == 'GT-LBS-RG-230':
            row['questions'][0]['question'] = 'Which providers should we evaluate?'
        if row['record_id'] == 'GT-LBS-DM-034':
            row['questions'] = [{'question': 'Which country is your billing account based in?', 'facts': ['billing_country']}]
        if row['record_id'] == 'GT-LBS-DIR-049':
            for question in row['questions']:
                if question['facts'] == ['max_stops']:
                    question['question'] = 'Will the 15–20 outlets be visited in one route, and how many must be included in one request?'
        if row['questions'] != previous:
            changes.append({'record_id': row['record_id'], 'before': previous, 'after': row['questions']})
    reviewed['status'] = 'locked_assistant_reviewed_working_reference'
    reviewed['independent_human_acceptance'] = False
    reviewed['scope'] = 'Separate development reference only; original GT is unchanged. No new workload or retention-duration requirements were silently added.'
    (OUT / 'reviewed-reference.json').write_text(json.dumps(reviewed, ensure_ascii=False, indent=2) + '\n')
    (OUT / 'reference-changes.json').write_text(json.dumps(changes, ensure_ascii=False, indent=2) + '\n')
    manifest = {'cases': 36, 'frozen_cases': 0, 'holdout_cases': 0, 'retrieval': 'BM25',
                'runtime': str(RUNTIME), 'baseline_runtime': str(ROOT / 'work/fact-binding/before'),
                'code_hashes': {str(p.relative_to(RUNTIME)): digest(p) for p in (RUNTIME / 'copilot').rglob('*.py')},
                'baseline_hashes': {str(p.relative_to(ROOT / 'work/fact-binding/before')): digest(p)
                                    for p in (ROOT / 'work/fact-binding/before/copilot').rglob('*.py')},
                'workbook_sha256': digest(REPO / 'data/ground-truth.xlsx'),
                'cases_sha256': digest(OUT / 'review-cases.json'),
                'original_gold_sha256': digest(OUT / 'locked-gold.json'),
                'reviewed_reference_sha256': digest(OUT / 'reviewed-reference.json'),
                'comparison': 'Paired before and after; shared completion cache for identical requests. Both methods include validation repair and monthly-workload normalization.'}
    (OUT / 'run-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'locked': True, 'cases': 36, 'reference_changes': len(changes),
                      'reviewed_questions': sum(len(r['questions']) for r in reviewed['cases'])}))


if __name__ == '__main__':
    main()
