# Historical migration and public reports verification

The public profile hosts authenticated reports alongside Langfuse and media storage. Reports are collected into a filtered bundle, checked against source hashes and mounted read-only. The bundle excludes runtime and source snapshots, credentials, databases, model assets and raw input/generation journals. Updating it recreates only the report container; Compose reconciles the other services normally.

- **58 focused tests passed** across evaluation, observability, public configuration, migration guards and report browsing.
- The reports-only image builds. A temporary localhost proxy rejects unauthenticated and incorrect-password requests, accepts the synthetic reports login, and protects the health/websocket routes. The dashboard restarts with its read-only mount intact.
- The filtered bundle contains **2,680 report files**, each verified byte-identical to its source. Both final runs render all 29 metrics and reproduce saved aggregates exactly. Legacy reports retain their original catalogs.
- A synthetic Docker-volume archive/restore preserves contents, ownership, permissions and symlinks. Migration tests reject running sources, changed checksums, different architectures, mismatched credentials and existing target volumes.
- The source history check read **four existing generation traces** across frozen and holdout runs and saved their observation IDs. This created no traces and made no inference calls.
- Frozen/holdout input, generation, record, manifest and summary files are unchanged from the pre-change commit. GT is unchanged. The original automatic-judge failures, approved AC-050 adjudication and provisional holdout-review status remain in the saved reports.
- Configured-secret scans passed for changed files and all staged report files. Temporary report/proxy containers and test volumes were removed. Existing local Langfuse services and data were untouched.

One intermediate verification assertion incorrectly required 29 metrics in the older 25-metric smoke artifact. The check was narrowed to the two final runs; no historical report was rewritten.

No public Langfuse deployment or real-data migration was performed. Real DNS/TLS, browser login, media access and full destination-stack restore/restart still need verification on the destination server. Cold migration requires matching Docker CPU architecture and pinned backend versions; cross-architecture logical migration is outside this helper.

Follow the [public setup](../../../copilot/observability/langfuse/PUBLIC_DEPLOYMENT.md) and [historical migration procedure](../../../copilot/observability/langfuse/HISTORICAL_MIGRATION.md). All checks use saved artifacts or synthetic fixtures; do not rerun frozen or holdout evaluations to populate the deployment.
