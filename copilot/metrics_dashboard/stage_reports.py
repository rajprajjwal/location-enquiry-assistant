"""Publish a filtered copy of saved reports without copying runtime state."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile

from copilot.metrics_dashboard.reports import available_reports
from copilot.paths import REPO_ROOT

FORMAT='copilot-saved-reports-v1'


def stage(repo,output):
    repo,output=Path(repo).resolve(),Path(output).resolve()
    previous=output.with_name(output.name+'.previous')
    if previous.exists():
        raise ValueError('An earlier staging backup exists; inspect it before replacing the bundle')
    if output.exists():
        marker=output/'bundle-manifest.json'
        if output.is_symlink() or not marker.exists() or json.loads(marker.read_text()).get('format')!=FORMAT:
            raise ValueError('Refusing to replace a directory that is not a generated report bundle')
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix=output.name+'.next-',dir=output.parent))
    manifest={'format':FORMAT,'sha256':{},'inference_calls':0}
    try:
        for source in available_reports(repo):
            relative=source.relative_to(repo)
            destination=temporary/relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            contents=source.read_bytes()
            destination.write_bytes(contents)
            destination.chmod(0o644)
            manifest['sha256'][str(relative)]=sha256(contents).hexdigest()
        (temporary/'bundle-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        for directory in temporary.rglob('*'):
            if directory.is_dir(): directory.chmod(0o755)
        temporary.chmod(0o755)
        if output.exists():
            output.rename(previous)
        try:
            temporary.rename(output)
        except Exception:
            if previous.exists(): previous.rename(output)
            raise
        if previous.exists(): shutil.rmtree(previous)
    finally:
        if temporary.exists(): shutil.rmtree(temporary)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=REPO_ROOT/'copilot/observability/runtime/report-bundle')
    args=parser.parse_args()
    result=stage(REPO_ROOT,args.out)
    print(f"Prepared {len(result['sha256'])} saved reports; no inference calls.")


if __name__=='__main__':main()
