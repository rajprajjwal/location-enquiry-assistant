"""Lock working inputs, original labels and separate reference corrections."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')
OUT = ROOT / 'outputs/clarification-routing-working'
RUNTIME = ROOT / 'work/clarification-routing/runtime'
SOURCE = ROOT / 'outputs/fact-binding-working/final'


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
    shutil.copy2(SOURCE / 'reviewed-reference.json', OUT / 'reviewed-reference.json')
    shutil.copy2(SOURCE / 'reference-changes.json', OUT / 'reference-changes.json')
    manifest = {'cases': 36, 'frozen_cases': 0, 'holdout_cases': 0, 'retrieval': 'BM25',
                'runtime': str(RUNTIME), 'baseline_runtime': str(ROOT / 'work/clarification-routing/before'),
                'code_hashes': {str(p.relative_to(RUNTIME)): digest(p) for p in (RUNTIME / 'copilot').rglob('*.py')},
                'baseline_hashes': {str(p.relative_to(ROOT / 'work/clarification-routing/before')): digest(p)
                                    for p in (ROOT / 'work/clarification-routing/before/copilot').rglob('*.py')},
                'workbook_sha256': digest(REPO / 'data/ground-truth.xlsx'),
                'cases_sha256': digest(OUT / 'review-cases.json'),
                'original_gold_sha256': digest(OUT / 'locked-gold.json'),
                'reviewed_reference_sha256': digest(OUT / 'reviewed-reference.json'),
                'comparison': 'Paired before and after route/selection fixes; identical-request cache shared. Original and prior reviewed working references unchanged.'}
    (OUT / 'run-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'locked': True, 'cases': 36, 'labels_changed': False}))


if __name__ == '__main__':
    main()
