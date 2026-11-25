"""Check schema-generated models in an isolated copy of the project inputs."""
from pathlib import Path
from tempfile import TemporaryDirectory
from hashlib import sha256
import json,os,shutil,subprocess,sys

OUT=Path(__file__).resolve().parent
REPO=OUT.parents[1]
with TemporaryDirectory(prefix='copilot-model-drift-') as temp:
    root=Path(temp)
    for name in ['contracts','schemas']:
        shutil.copytree(REPO/name,root/name)
    (root/'scripts').mkdir()
    shutil.copy2(REPO/'scripts/gen_models.py',root/'scripts/gen_models.py')
    env=os.environ.copy()
    env['PYTHONPATH']=str(REPO)
    result=subprocess.run([sys.executable,'-B',str(root/'scripts/gen_models.py')],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (OUT/'model-drift.log').write_text(result.stdout)
    actual=root/'copilot/models/generated'
    expected=REPO/'copilot/models/generated'
    before={p.name:sha256(p.read_bytes()).hexdigest() for p in expected.glob('*.py')}
    after={p.name:sha256(p.read_bytes()).hexdigest() for p in actual.glob('*.py')}
    differences=[name for name in sorted(before.keys()|after.keys()) if before.get(name)!=after.get(name)] if result.returncode==0 else []
    summary={'exit_code':result.returncode,'passed':result.returncode==0 and not differences,'differing_files':differences,'tracked_models_modified':False,'expected':before,'generated':after}
    (OUT/'model-drift.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['expected','generated']}))
    raise SystemExit(not summary['passed'])
