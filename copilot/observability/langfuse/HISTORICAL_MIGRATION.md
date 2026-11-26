# Move existing traces and reports

Use this procedure to move the existing Langfuse databases and object storage during a maintenance window. The source stack must be stopped for the copy. It makes no chat or embedding calls, regenerates no answers, rescores no cases and publishes no new evaluation traces. Saved evaluation reports come from the checkout; trace history comes from the private backup.

## Prerequisites

- Use the same pinned base Compose file and backend image versions on both hosts. The cold-volume procedure requires the **same Docker CPU architecture**: for a Mac ARM source, use a Linux ARM64 destination. The restore command refuses architecture mismatches. For an AMD64 destination, use a separately rehearsed logical PostgreSQL dump and native ClickHouse backup/restore instead; do not copy the raw database volumes across architectures.
- Install Docker, its Compose plugin and Python 3.12. Install `.[observability,evaluation]` in the activated environment. Commands below use `python`; `python3` works identically after activation.
- Keep backups on encrypted storage outside Git, with access restricted to the operator. The bundle includes passwords, project API keys, encrypted database contents and the encryption key. Do not upload it to the repository or include it in the report browser.
- Reserve a new destination with **no existing public-stack data volumes**. Restore refuses to overwrite any destination volume. Existing source volumes remain available for rollback.
- Set up the three public hostnames described in [public deployment](PUBLIC_DEPLOYMENT.md). Do not start the new public stack before restoring its volumes.

## 1. Record a read-only source check

On the source machine, from the repository root:

```sh
python -m copilot.observability.verification.verify_history \
  --env-file copilot/observability/runtime/langfuse.env \
  --out copilot/observability/runtime/history-source.json
```

This reads two existing generation traces from each final run and records their observation IDs. It also hashes the input, generation, score, summary and manifest files for the 80 frozen and 96 holdout cases. It creates no traces and makes no inference calls. Preserve this check alongside the backup; a missing historical trace must be investigated before migration.

## 2. Pause writers and create a stopped-stack backup

Stop any enquiry application or evaluation process exporting to this Langfuse project. Do not restart evaluation runners to create missing traces. Allow pending exports and worker jobs to finish, then:

```sh
python -m copilot.observability.langfuse_local stop
python -m copilot.observability.langfuse_migration backup \
  --project location-enquiry-langfuse \
  --env-file copilot/observability/runtime/langfuse.env \
  --bundle copilot/observability/runtime/migration-001
python -m copilot.observability.langfuse_migration verify \
  --bundle copilot/observability/runtime/migration-001
```

The helper checks that source containers are stopped and source volumes are complete. It streams private archives of PostgreSQL, Redis, ClickHouse data/logs and MinIO through Docker, avoiding a host bind mount. The bundle contains `private.env` and a checksum manifest. If backup is interrupted before a valid manifest is written, resolve the failure and create a new bundle.

The source can be restarted for read-only inspection after backup. Keep exporters paused to avoid diverging histories during cutover. If source writes resume, take a new consistent backup before the final cutover.

## 3. Transfer privately and prepare the destination

Use SSH/SCP or your encrypted backup transport to copy `migration-001` and `history-source.json` to a private directory on the destination. For example, after creating `/srv/private/location-migration` with mode 0700 on the server:

```sh
scp -r copilot/observability/runtime/migration-001 \
  deploy@your-server:/srv/private/location-migration/
scp copilot/observability/runtime/history-source.json \
  deploy@your-server:/srv/private/location-migration/
```

On the destination, check out the same deployment revision, activate the environment and run:

```sh
python -m copilot.observability.langfuse_migration verify \
  --bundle /srv/private/location-migration/migration-001
python -m copilot.observability.langfuse_public prepare \
  --domain traces.example.com --media-domain media.example.com \
  --reports-domain reports.example.com \
  --admin-email existing-admin@example.com --acme-email operations@example.com \
  --migrate-env-file /srv/private/location-migration/migration-001/private.env
python -m copilot.observability.langfuse_public config
python -m copilot.observability.langfuse_migration restore \
  --project location-enquiry-langfuse-public \
  --env-file copilot/observability/runtime/langfuse-public.env \
  --bundle /srv/private/location-migration/migration-001
```

Preparation copies the original database/storage credentials, salt, encryption key, session secret and project API keys. It creates separate reports-login credentials. **Existing Langfuse accounts and passwords remain unchanged**; the administrator bootstrap settings do not rename or reset a restored account. Use the original account to sign in. Preparation refuses an existing destination configuration; do not regenerate credentials over restored databases.

Before creating unused destination volumes, restore verifies every archive checksum, the CPU architecture and the base Compose fingerprint. A partial restore is not retried or overwritten automatically. Inspect any new destination volumes before choosing another clean destination. Keep source volumes intact for recovery.

## 4. Start and verify before cutover

```sh
python -m copilot.observability.langfuse_public up
curl --fail https://traces.example.com/api/public/health
python -m copilot.observability.verification.verify_history \
  --env-file copilot/observability/runtime/langfuse-public.env \
  --reference /srv/private/location-migration/history-source.json \
  --out copilot/observability/runtime/history-restored.json
```

Require `passed: true`. Saved reports must match their source bytes, and the four sampled historical traces must retain the same observation IDs. This verifies the sample, not every historical trace. Also open older traces and attachments in Langfuse.

Open `https://reports.example.com`, sign in with `REPORTS_USER` and `REPORTS_PASSWORD` from the private destination file, and inspect **Evaluation metrics** and **Saved activity reports**. Confirm the frozen and holdout scores, the AC-050 adjudication and provisional holdout-review note. No chat/embedding credentials are needed for report viewing. A fresh checkout without the volume restore shows saved report files but does not recreate historical Langfuse traces.

Run the synthetic ingestion/media/login checks in the public guide, then stop and restart the full public stack and repeat history verification with a new output filename. Only after this passes should applications switch their exporter URL to the public project. Keep the source stopped during normal operation after cutover.

## Rollback

Pause exporters, stop the destination stack without deleting volumes, restore the original exporter URL and start the original local stack. Its data is preserved. Writes accepted only by the destination after cutover will not appear on the old source; reconcile or back up that destination before rolling back. Do not run both stacks as active ingestion targets during rollback.

The cold-copy approach follows [Langfuse's Docker backup guidance](https://langfuse.com/self-hosting/configuration/backups). For different architectures or a move to managed databases, use its PostgreSQL, native ClickHouse and object-storage migration guidance and rehearse the logical restore independently.
