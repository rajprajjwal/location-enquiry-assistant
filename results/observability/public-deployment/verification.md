# Public deployment verification

- Automated suite: **1,171 passed, 1 skipped; 15 subtests passed** with real interpretation validation and prepared offline tokenizer assets. The existing freshness test requires a local raw-corpus snapshot.
- Docker Compose: public configuration resolves successfully; public project and volumes are separate from local deployment. Databases have no published ports, and direct dashboard/storage ports remain loopback-only.
- Proxy: the original Caddyfile validates. Trusted local HTTPS reaches dashboard health and media storage; HTTP redirects to HTTPS.
- Media: signed upload, download and deletion pass through the HTTPS media route.
- Tracing: all three synthetic spans are exported and read back through HTTPS. No model calls were made.
- Restart: the isolated proxy restarts successfully. The existing local stack and its original ingestion smoke test continue to work.
- Package: the wheel builds and includes both Compose profiles and Caddyfile, without runtime secrets. The base local Compose file is unchanged.

The initial broad test attempt used an empty default tokenizer cache and failed to download assets under network restrictions. The complete rerun used the prepared offline cache and passed.

Verification used an isolated loopback proxy with a trusted internal CA against the existing local backend. Docker file copying avoided the macOS restriction on mounting files from Documents. The proxy was removed after checks.

Destination-host checks remain before rollout: real DNS and ACME issuance, browser login, media access, public ingestion and full-stack persistence on Linux. The public configuration is implemented, but those checks are still pending. The public deployment guide provides the commands.