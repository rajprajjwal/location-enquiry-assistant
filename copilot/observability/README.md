# End-to-end tracing

Trace each enquiry from interpretation through workflow steps, model attempts, tools, validation and conversation-state updates. Each run records latency in milliseconds, endpoint-reported token usage and reporting cost. Bucket, API and team labels support filtering without storing prompts or completions in tracing metadata.

## Setup

Follow [application deployment](../../docs/deployment.md) first and activate its Python 3.12 environment. Install the optional OTLP exporter using either command:

```sh
python -m pip install -e '.[observability]'
```

```sh
python3 -m pip install -e '.[observability]'
```

Install and start Docker Desktop, then prepare the local service:

```sh
python -m copilot.observability.langfuse_local up
```

Or:

```sh
python3 -m copilot.observability.langfuse_local up
```

The first start downloads the pinned service images and creates private credentials at `copilot/observability/runtime/langfuse.env`. This ignored file must stay outside Git. Docker volumes preserve the project and traces across stops.

Open http://localhost:3000. Log in as `local-admin@localhost.test`, using `LANGFUSE_ADMIN_PASSWORD` from the private file. Wait until the health endpoint responds before testing ingestion:

```sh
curl --fail http://localhost:3000/api/public/health
python -m copilot.observability.verification.langfuse_smoke --out copilot/observability/runtime/smoke-check
```

Use a new output folder for each smoke run. The smoke creates synthetic observations and makes no model calls. A healthy web endpoint alone does not establish successful trace ingestion.

To resume existing containers without downloading images, use `python -m copilot.observability.langfuse_local start`. Use `status` to inspect containers and `stop` to stop them without removing volumes. All module commands also work with `python3`.

## Enable tracing for the application

Set these in the terminal used to launch the app:

```sh
export COPILOT_TRACE_EXPORT=langfuse-local
python -m streamlit run copilot/streamlit_ui/streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

Configure chat credentials, certificates and retrieval using the deployment guide before testing a live enquiry. Restart the application after changing export mode or pricing. With no export setting, complete traces remain local in the case database. Remote export runs in the background with a 30-second request timeout; export failures do not change the enquiry response.

The app includes an instrumented trace explorer alongside its existing enquiry details. Filter by bucket, API, team, latency and INR reporting cost. Langfuse records the same trace and span IDs, bucket tags and root metadata. Native Langfuse cost fields are USD; the explorer and `cost_inr` metadata use INR.

Inspect a saved verification database separately:

```sh
export COPILOT_TRACE_DB=results/observability/working-verified/traces.db
python -m streamlit run copilot/observability/streamlit_app.py --server.address 127.0.0.1 --server.port 8502
```

## Cost interpretation

The institute endpoints are free: actual endpoint charge is **₹0**. Reporting estimates use explicit illustrative rates per million tokens: input $0.10, output $0.20 and embedding $0.02, converted at ₹94/USD. These are assumptions, not institute prices or billed charges. Edit `copilot/config/observability.yaml`, or set `COPILOT_TRACE_RATES_FILE` to another rate card.

Usage is counted once per physical endpoint attempt, including retries when usage is returned. Missing usage remains explicit and yields an incomplete estimate; unknown rates remain unpriced. Parent spans are not added again. Root latency measures elapsed enquiry time; nested span durations must not be summed as total latency because they overlap.

## Verification and deletion

Working-eval verification replays the same recorded model replies with tracing disabled and checks business outputs, routes, pending replies and approvals for changes. This replay makes no additional live model calls. Frozen verification checks tracing completeness only; it does not rescore answer quality. Frozen inputs are validated against the pinned 80-case export, and bucket/API/team labels are used only as trace metadata. Holdout cases are excluded.

Deleting an enquiry removes its local trace in the same transaction. A separate queue submits deletion of any Langfuse copy after exports finish. Submission is distinct from confirmed removal: Langfuse deletes asynchronously. Failed submissions remain pending and can be retried from the UI or with:

```sh
python -m copilot.observability.sync_deletions --db copilot/case_storage/data/lbs.db
```

Pending approvals linked only to the deleted enquiry are cancelled. Decided approvals remain in the audit log with their source marked deleted. Runtime credentials, databases and Docker volumes are not committed; verification summaries and per-record trace checks are saved under `results/observability/`.

## Public HTTPS deployment

Use the separate [public deployment guide](langfuse/PUBLIC_DEPLOYMENT.md) to host Langfuse on a Docker server. It uses separate credentials, containers and volumes; the local commands above remain unchanged.
