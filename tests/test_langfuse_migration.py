"""Migration refuses unsafe sources, altered bundles and existing targets."""
import json
from pathlib import Path
from unittest.mock import patch
import pytest

from copilot.observability import langfuse_migration as migration
from copilot.observability import langfuse_public as public
from copilot.observability.langfuse_local import load_environment


def bundle(tmp_path):
    source=tmp_path/'source.env'
    public.prepare(source,'traces.example.com','media.example.com','admin@example.com','ops@example.com')
    folder=tmp_path/'bundle'
    folder.mkdir()
    (folder/'private.env').write_bytes(source.read_bytes())
    for name in migration.VOLUMES:
        (folder/(name+'.tar.gz')).write_bytes(b'synthetic backup fixture')
    manifest={'format':1,'architecture':'arm64','base_compose_sha256':migration.checksum(migration.COMPOSE),
              'sha256':{p.name:migration.checksum(p) for p in folder.iterdir()}}
    (folder/'manifest.json').write_text(json.dumps(manifest))
    return folder,source


def test_migration_preserves_credentials_but_separates_report_login(tmp_path):
    folder,source=bundle(tmp_path)
    destination=tmp_path/'target.env'
    public.prepare(destination,'new.example.com','media.new.example.com','admin@example.com','ops@example.com',
                   reports_domain='reports.new.example.com',migrate_env_file=folder/'private.env')
    old,new=load_environment(source),load_environment(destination)
    assert all(old[key]==new[key] for key in public.MIGRATION_KEYS)
    assert old['REPORTS_PASSWORD']!=new['REPORTS_PASSWORD']


def test_bundle_tampering_is_detected_before_docker(tmp_path):
    folder,_=bundle(tmp_path)
    migration.verify_bundle(folder)
    (folder/'minio-data.tar.gz').write_bytes(b'changed')
    with pytest.raises(ValueError,match='checksum mismatch'):
        migration.verify_bundle(folder)


def test_running_stack_cannot_be_backed_up(tmp_path,monkeypatch):
    monkeypatch.setattr(migration,'docker',lambda *args:'running-container')
    with pytest.raises(ValueError,match='Stop every container'):
        migration.backup(tmp_path/'new',tmp_path/'unused','source')
    assert not (tmp_path/'new').exists()


def test_stopped_backup_streams_all_archives_and_hashes_private_config(tmp_path,monkeypatch):
    import gzip
    source=tmp_path/'source.env'
    public.prepare(source,'traces.example.com','media.example.com','admin@example.com','ops@example.com')
    def docker(*args):
        if args[0]=='ps': return ''
        if args[:2]==('volume','ls'): return '\n'.join(migration.VOLUMES)
        if args[:2]==('volume','inspect'):
            return json.dumps([{'Name':n,'Labels':{'com.docker.compose.volume':n}} for n in migration.VOLUMES])
        if args[0]=='info': return 'aarch64'
        raise AssertionError(args)
    monkeypatch.setattr(migration,'docker',docker)
    monkeypatch.setattr(migration,'docker_command',lambda:'docker')
    def run(command,stdout,check):
        assert ':ro' in command[command.index('-v')+1]
        stdout.write(gzip.compress(b'synthetic archive bytes'))
    monkeypatch.setattr(migration.subprocess,'run',run)
    target=tmp_path/'stopped-copy'
    migration.backup(target,source,'synthetic-source')
    manifest=migration.verify_bundle(target)
    assert manifest['architecture']=='arm64' and len(manifest['sha256'])==6
    assert (target/'private.env').read_bytes()==source.read_bytes()
    assert all((target/name).stat().st_mode & 0o777==0o600 for name in manifest['sha256'])


@pytest.mark.parametrize('mode',['architecture','credentials','existing'])
def test_restore_fails_before_any_volume_is_created(tmp_path,monkeypatch,mode):
    folder,source=bundle(tmp_path)
    calls=[]
    def docker(*args):
        calls.append(args)
        if args[0]=='ps': return ''
        if args[:2]==('volume','ls'):
            return 'location-enquiry-langfuse-public_postgres-data' if mode=='existing' else ''
        raise AssertionError('Unexpected Docker mutation')
    monkeypatch.setattr(migration,'docker',docker)
    monkeypatch.setattr(migration,'architecture',lambda:'amd64' if mode=='architecture' else 'arm64')
    if mode=='credentials':
        source.write_text(source.read_text().replace('POSTGRES_PASSWORD=','POSTGRES_PASSWORD=changed'))
    with pytest.raises(ValueError):
        migration.restore(folder,source,'location-enquiry-langfuse-public')
    assert not any(c[:2]==('volume','create') for c in calls)


def test_restore_streams_only_to_unused_public_volumes(tmp_path,monkeypatch):
    folder,source=bundle(tmp_path)
    calls=[]
    monkeypatch.setattr(migration,'architecture',lambda:'arm64')
    monkeypatch.setattr(migration,'docker',lambda *args:calls.append(args) or '')
    monkeypatch.setattr(migration,'docker_command',lambda:'docker')
    with patch.object(migration.subprocess,'run') as run:
        migration.restore(folder,source,'location-enquiry-langfuse-public')
    assert len([c for c in calls if c[:2]==('volume','create')])==5
    assert run.call_count==5
    assert all('location-enquiry-langfuse-public_' in ' '.join(c.args[0]) for c in run.call_args_list)


def test_reports_upgrade_preserves_all_existing_credentials(tmp_path):
    path=tmp_path/'public.env'
    public.prepare(path,'traces.example.com','media.example.com','admin@example.com','ops@example.com')
    before=load_environment(path)
    path.write_text(''.join(f'{k}={v}\n' for k,v in before.items() if not k.startswith('REPORTS_')))
    assert public.main(['configure-reports','--env-file',str(path),'--reports-domain','reports.example.com'])==0
    after=load_environment(path)
    assert all(after[k]==before[k] for k in before if not k.startswith('REPORTS_'))
    assert path.stat().st_mode & 0o777==0o600


def test_up_recreates_report_mount_after_staging_without_forcing_database_restart(tmp_path):
    target=tmp_path/'public.env'
    public.prepare(target,'traces.example.com','media.example.com','admin@example.com','ops@example.com')
    with patch.object(public,'docker_command',return_value='docker'), \
         patch.object(public.subprocess,'run') as run, \
         patch('copilot.metrics_dashboard.stage_reports.stage') as stage:
        assert public.main(['up','--env-file',str(target)])==0
    stage.assert_called_once()
    commands=[call.args[0] for call in run.call_args_list]
    assert commands[-2][-5:]==['up','-d','--build','--force-recreate','evaluation-reports']
    assert commands[-1][-2:]==['up','-d']
