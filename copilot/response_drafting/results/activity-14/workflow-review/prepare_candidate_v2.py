"""Freeze the next controlled workflow trial without importing concurrent ownership edits."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

WORK = Path(__file__).resolve().parent
REPO = Path('/Users/shahidkamal/Documents/test-project/location-enquiry-assistant')
source, target = WORK / 'candidate', WORK / 'candidate-v2'
if target.exists():
    raise SystemExit('Snapshot already exists; use its recorded hashes.')
shutil.copytree(source, target, symlinks=True)
changed = ['copilot/diagnostics/policy.py', 'copilot/safety/incident_evidence.py',
           'copilot/qualification/requirements.py', 'copilot/qualification/wording.py']
for relative in changed:
    shutil.copy2(REPO / relative, target / relative)
for name in ('contracts', 'schemas', 'vocab'):
    link = target / name
    link.unlink()
    shutil.copytree(REPO / name, link, ignore=shutil.ignore_patterns('__pycache__', '.DS_Store'))
manifest = {'parent': str(source), 'runtime': str(target), 'changed_files': changed,
            'ownership': 'Same locked implementation as the baseline and first trial.',
            'code_sha256': {str(p.relative_to(target)): sha256(p.read_bytes()).hexdigest()
                            for p in (target/'copilot').rglob('*.py') if 'results' not in p.parts},
            'schema_sha256': {str(p.relative_to(target)): sha256(p.read_bytes()).hexdigest()
                              for name in ('contracts','schemas','vocab') for p in (target/name).rglob('*') if p.is_file()}}
(REPO/'copilot/response_drafting/results/activity-14/workflow-review/candidate-v2-lock.json').write_text(json.dumps(manifest, indent=2)+'\n')
print({'python_files':len(manifest['code_sha256']), 'changed':changed})
