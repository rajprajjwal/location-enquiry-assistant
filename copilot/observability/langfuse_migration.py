"""Copy a stopped Langfuse stack to unused volumes without running inference."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess

from .langfuse_local import COMPOSE, RUNTIME, docker_command, load_environment
from .langfuse_public import MIGRATION_KEYS
from copilot.paths import REPO_ROOT

VOLUMES=('postgres-data','redis-data','clickhouse-data','clickhouse-logs','minio-data')
ARCHIVE_IMAGE='alpine:3.22.2'


def checksum(path):
    value=sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            value.update(block)
    return value.hexdigest()


def docker(*args):
    return subprocess.check_output([docker_command(),*args],text=True).strip()


def require_stopped(project):
    if docker('ps','--filter',f'label=com.docker.compose.project={project}','--format','{{.ID}}'):
        raise ValueError('Stop every container in this Compose project before copying data')


def architecture():
    value=docker('info','--format','{{.Architecture}}')
    return {'aarch64':'arm64','x86_64':'amd64'}.get(value,value)


def verify_bundle(bundle):
    bundle=Path(bundle)
    manifest=json.loads((bundle/'manifest.json').read_text())
    expected={'private.env',*(name+'.tar.gz' for name in VOLUMES)}
    if set(manifest['sha256'])!=expected or manifest['format']!=1:
        raise ValueError('Unexpected migration bundle format')
    for name,expected_hash in manifest['sha256'].items():
        path=bundle/name
        if path.is_symlink() or checksum(path)!=expected_hash:
            raise ValueError('Migration bundle checksum mismatch: '+name)
    if manifest['base_compose_sha256']!=checksum(COMPOSE):
        raise ValueError('Use the same pinned base Compose configuration for restoration')
    return manifest


def backup(bundle,env_file,project):
    location=Path(bundle).resolve()
    if location.is_relative_to(REPO_ROOT.resolve()) and not location.is_relative_to(RUNTIME.resolve()):
        raise ValueError('Keep private bundles outside Git or inside the ignored observability runtime directory')
    require_stopped(project)
    names=docker('volume','ls','--filter',f'label=com.docker.compose.project={project}','--format','{{.Name}}').splitlines()
    descriptions=json.loads(docker('volume','inspect',*names)) if names else []
    sources={(r.get('Labels') or {}).get('com.docker.compose.volume'):r['Name'] for r in descriptions}
    if not all(name in sources for name in VOLUMES):
        raise ValueError('The source project does not have all five Langfuse data volumes')
    values=load_environment(env_file)
    if any(not values.get(key) for key in MIGRATION_KEYS):
        raise ValueError('Source configuration is missing required migration credentials')
    bundle=Path(bundle)
    bundle.mkdir(mode=0o700,parents=True,exist_ok=False)
    shutil.copyfile(env_file,bundle/'private.env')
    os.chmod(bundle/'private.env',0o600)
    manifest={'format':1,'architecture':architecture(),'source_project':project,
              'base_compose_sha256':checksum(COMPOSE),'sha256':{},'inference_calls':0}
    for name in VOLUMES:
        target=bundle/(name+'.tar.gz')
        descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'wb') as stream:
            subprocess.run([docker_command(),'run','--rm','--network','none',
                '-v',sources[name]+':/volume:ro',ARCHIVE_IMAGE,'tar','czf','-','-C','/volume','.'],stdout=stream,check=True)
    for name in ('private.env',*(name+'.tar.gz' for name in VOLUMES)):
        manifest['sha256'][name]=checksum(bundle/name)
    (bundle/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Stopped-stack backup complete. Keep the entire bundle private and encrypted in transit.')


def restore(bundle,env_file,project):
    if project!='location-enquiry-langfuse-public':
        raise ValueError('Restoration is restricted to the separate public project')
    manifest=verify_bundle(bundle)
    require_stopped(project)
    if architecture()!=manifest['architecture']:
        raise ValueError('Cold-volume restore requires the same Docker architecture; use logical database migration for a different architecture')
    old=load_environment(Path(bundle)/'private.env')
    new=load_environment(env_file)
    if any(old.get(k)!=new.get(k) or not old.get(k) for k in MIGRATION_KEYS):
        raise ValueError('Prepare the destination with --migrate-env-file from this bundle first')
    existing=set(docker('volume','ls','--format','{{.Name}}').splitlines())
    targets={name:project+'_'+name for name in VOLUMES}
    if existing.intersection(targets.values()):
        raise ValueError('Destination data volumes already exist; restoration never overwrites them')
    for name,volume in targets.items():
        docker('volume','create','--label',f'com.docker.compose.project={project}',
               '--label',f'com.docker.compose.volume={name}',volume)
        with (Path(bundle)/(name+'.tar.gz')).open('rb') as stream:
            subprocess.run([docker_command(),'run','--rm','-i','--network','none',
                '-v',volume+':/volume',ARCHIVE_IMAGE,'tar','xzpf','-','-C','/volume'],stdin=stream,check=True)
    print('Restored to unused public volumes. Existing users, project keys and traces are preserved; verify before cutover.')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('backup','verify','restore'))
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--env-file',type=Path)
    parser.add_argument('--project')
    args=parser.parse_args(argv)
    try:
        if args.action=='verify':
            verify_bundle(args.bundle)
            print('Bundle checksums and pinned Compose configuration match; no endpoint calls.')
        else:
            if not args.env_file or not args.project:
                parser.error('backup/restore require --env-file and --project')
            {'backup':backup,'restore':restore}[args.action](args.bundle,args.env_file,args.project)
    except (ValueError,KeyError,FileNotFoundError,FileExistsError) as error:
        parser.error(str(error))


if __name__=='__main__':
    main()
