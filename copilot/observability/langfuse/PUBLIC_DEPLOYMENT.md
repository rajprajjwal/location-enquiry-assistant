# Public Langfuse deployment

Host Langfuse on one HTTPS domain, browser media on a second, and saved evaluation/activity reports on a third. Caddy obtains and renews certificates and forwards requests to private Docker services. This is a single-server deployment, without high availability. Local Langfuse uses its existing configuration independently.

**To preserve existing traces, follow [historical migration](HISTORICAL_MIGRATION.md) before starting a fresh stack.** Git contains saved report artifacts, but Langfuse history is stored in its database and object-storage volumes. Neither deployment nor report viewing reruns frozen or holdout evaluations.

## Before starting

Use a Linux server with Docker Engine and the Compose plugin, persistent disk and sufficient CPU/RAM for Langfuse, ClickHouse, PostgreSQL, Redis and object storage. Follow the upstream [host sizing guidance](https://langfuse.com/self-hosting/deployment/docker-compose). Python 3.12 is required for the project commands.

1. Check out the repository and activate a Python 3.12 environment. Run `python -m pip install -e '.[observability,evaluation]'` (or `python3 -m pip install -e '.[observability,evaluation]'`). For report viewing alone, skip model keys, tokenizer downloads and retrieval-index rebuilding in the application guide. The report container installs its dependencies during the first build; allow outbound access to the image and Python package registries.
2. Point three DNS A records, for example `traces.example.com`, `media.example.com` and `reports.example.com`, at the server. Publish AAAA records only if IPv6 reaches the server too. Use dedicated hostnames without a URL path.
3. Allow inbound TCP 80 and 443. Keep database, Redis, ClickHouse and storage ports private. Caddy needs outbound access for certificate issuance. Ports 80 and 443 must be available; this profile assumes there is no existing reverse proxy using them.
4. Choose an administrator email and certificate contact email. Keep Docker daemon access restricted to server administrators.

Run every command below from the repository root. Each `python` command also works with `python3`.

## Prepare private configuration

```sh
python -m copilot.observability.langfuse_public prepare \
  --domain traces.example.com \
  --media-domain media.example.com \
  --reports-domain reports.example.com \
  --admin-email admin@example.com \
  --acme-email operations@example.com
```

Alternatively:

```sh
python3 -m copilot.observability.langfuse_public prepare \
  --domain traces.example.com \
  --media-domain media.example.com \
  --reports-domain reports.example.com \
  --admin-email admin@example.com \
  --acme-email operations@example.com
```

Replace the example values with real domains and emails. This creates ignored, mode-0600 `copilot/observability/runtime/langfuse-public.env`. It contains the generated administrator password, API keys, database passwords and encryption key. Keep an encrypted backup outside the server. Preparation refuses to overwrite it. Do not regenerate credentials against existing volumes: changing bootstrap values does not rotate existing users or project keys.

The public project uses separate named volumes and loopback ports 3001 and 9091, leaving the local stack on 3000 and 9090. If those ports are occupied, edit `LANGFUSE_PORT` and `LANGFUSE_BLOB_PORT` in the public file before starting. Public clients use HTTPS on 443.

For an existing public configuration created without reports fields, install the updated extra and run the following once. This adds reports credentials without changing Langfuse/database credentials:

```sh
python -m copilot.observability.langfuse_public configure-reports --reports-domain reports.example.com
```

## Validate and start

```sh
python -m copilot.observability.langfuse_public config
python -m copilot.observability.langfuse_public up
python -m copilot.observability.langfuse_public status
curl --fail --show-error https://traces.example.com/api/public/health
```

`config` checks the domains and Compose configuration without printing secrets. `up` downloads the pinned images on first start. Initial database migrations and certificate issuance can take several minutes. The dashboard domain must match `NEXTAUTH_URL`; the media endpoint uses the separate HTTPS media domain, while service-to-service storage stays on the Docker network.

Open the dashboard and sign in with your administrator email and `LANGFUSE_ADMIN_PASSWORD` from the private file. Headless initialization creates the first user and project. Open signup is disabled. Invitations do not create new accounts while signup is disabled; plan additional accounts through the upstream [authentication guidance](https://langfuse.com/self-hosting/security/authentication-and-sso). This profile provides email/password login, without SMTP or SSO configuration.

## Open saved reports

Open `https://reports.example.com`. The browser prompts for `REPORTS_USER` and `REPORTS_PASSWORD` from the private file. This read-only reports login is separate from Langfuse. Caddy checks a bcrypt password hash over HTTPS and protects the entire report host, including Streamlit websocket traffic (see [Caddy authentication](https://caddyserver.com/docs/caddyfile/directives/basic_auth)). The report service has no published host port and receives neither model keys nor Langfuse project secrets.

**Evaluation metrics** displays the saved baseline/agent comparisons, including 80 frozen and 96 holdout cases. **Saved activity reports** searches Markdown, JSON, CSV, JSONL and text report artifacts. It displays files up to 5 MB and offers downloads. Other activities retain their original formats and review status rather than being silently converted to the evaluation metric schema. Use the visible Langfuse link to inspect execution traces.

Before startup, `up` builds a filtered copy in the ignored `copilot/observability/runtime/report-bundle/` directory. This includes root/component reports, annotation results and the selected data-review audits. Runtime snapshots, source snapshots, database files, model assets and raw gold/input/generation journals are excluded. Only this bundle is mounted read-only in the report service; no original runtime directories are mounted. The bundle manifest records file checksums. Commit intended report changes before publishing; the bundle reflects the current checkout, including allowed local artifacts, so inspect it before rollout. You can prepare it separately using `python -m copilot.metrics_dashboard.stage_reports` without starting any services.

Verify that unauthenticated access returns 401, then sign in and open both final runs and a saved component report. Refreshing or restarting this service reads saved artifacts only. After updating the checkout, run `langfuse_public up` again to rebuild the bundle and recreate the report container; the mounts refer to the generated bundle directories. This does not require inference. Do not run the protected holdout runner to populate the dashboard.

## Verify trace ingestion

```sh
python -m copilot.observability.verification.langfuse_smoke \
  --env-file copilot/observability/runtime/langfuse-public.env \
  --out copilot/observability/runtime/public-smoke-01
```

Use a new output folder each time. The check sends synthetic spans and verifies that all span IDs can be read back through the public API. It makes no model calls. Require `passed: true` in `report.json`, then confirm the synthetic trace appears in the dashboard. Also verify browser login and a media upload/download through the HTTPS media domain. A healthy web endpoint alone does not establish ingestion or media functionality.

## Connect the enquiry application

The application needs only these three values from the public configuration; never copy the full server credentials onto an application host:

```sh
export COPILOT_TRACE_EXPORT=langfuse
export LANGFUSE_BASE_URL=https://traces.example.com
export LANGFUSE_PUBLIC_KEY='<project public key>'
export LANGFUSE_SECRET_KEY='<project secret key>'
```

Use the deployment platform's secret store rather than committing keys or putting them in a shared launch script. Restart the application, submit a test enquiry and verify its trace. The shared exporter enforces HTTPS for remote endpoints. Public hosting does not change the local trace database or make the enquiry UI public. Deletion requests use the same project credentials and remain asynchronous; verify a synthetic enquiry deletion through the normal application workflow before rollout.

## Persistence, restart and recovery

```sh
python -m copilot.observability.langfuse_public stop
python -m copilot.observability.langfuse_public up
```

Confirm login and previously saved traces still work after restart, then rerun the synthetic check. Stopping preserves all volumes, including Caddy certificates. Do not use `docker compose down --volumes` unless intentionally deleting the deployment.

Back up the private configuration, PostgreSQL, ClickHouse and object-storage volumes using consistent snapshots or service-specific backup tools. Retain Redis and certificate state as part of a full stopped-stack snapshot. Test restoration on an isolated host before relying on backups. Preserve the same encryption key when restoring encrypted data. Upgrade pinned images deliberately after backing up and testing migrations.

For diagnostics use `docker compose --project-name location-enquiry-langfuse-public --env-file copilot/observability/runtime/langfuse-public.env -f copilot/observability/langfuse/compose.yaml -f copilot/observability/langfuse/compose.public.yaml logs --tail 100`. Treat logs as private. Certificate failures usually indicate DNS, firewall or port conflicts. Login redirects usually indicate a domain mismatch. Media failures require checking the media DNS and proxy route. Do not bypass TLS verification.

This profile is validated locally for configuration and proxy routing. Real certificate issuance, browser authentication and public ingestion must also pass on the destination server before rollout.
