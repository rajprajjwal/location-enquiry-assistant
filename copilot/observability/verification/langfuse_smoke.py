"""Check real local Langfuse ingestion with explicitly synthetic observations."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time

import httpx

from copilot.case_storage.db import connect
from copilot.observability.langfuse_local import load_environment
from copilot.observability.tracing import trace_run, observed_span, set_usage, provider


def fetch_observations(client, trace_id):
    now = datetime.now(timezone.utc)
    params = {"traceId": trace_id, "fromStartTime": (now - timedelta(days=1)).isoformat(),
              "toStartTime": (now + timedelta(minutes=5)).isoformat(),
              "fields": "core,basic,usage,metadata", "limit": 1000}
    data = []
    while True:
        response = client.get("/api/public/v2/observations", params=params)
        response.raise_for_status()
        body = response.json()
        data.extend(body.get("data", []))
        cursor = body.get("meta", {}).get("cursor")
        if not cursor:
            return data
        params["cursor"] = cursor


def verify(output):
    values = load_environment()
    os.environ["COPILOT_TRACE_EXPORT"] = "langfuse-local"
    output.mkdir(parents=True, exist_ok=False)
    with connect(output / "smoke.db") as con:
        with trace_run(connection=con, metadata={"record_id": "synthetic-trace-smoke", "bucket": "docs",
                                                 "split": "synthetic", "run_id": output.name}) as run:
            with observed_span("synthetic.operation", kind="workflow_step"):
                with observed_span("synthetic.generation", kind="llm_attempt", attributes={
                    "langfuse.observation.type": "generation", "langfuse.observation.model.name": "synthetic-not-a-live-model",
                }) as span:
                    set_usage(span, {"prompt_tokens": 10, "completion_tokens": 5})
        provider().force_flush(timeout_millis=10000)
        expected = set(run.spans)
        observations = []
        with httpx.Client(base_url=values["LANGFUSE_BASE_URL"],
                          auth=(values["LANGFUSE_PUBLIC_KEY"], values["LANGFUSE_SECRET_KEY"]), timeout=10) as client:
            for _ in range(12):
                observations = fetch_observations(client, run.trace_id)
                if expected <= {row["id"] for row in observations}:
                    break
                time.sleep(2)
        report = {"passed": expected <= {row["id"] for row in observations}, "trace_id": run.trace_id,
                  "local_span_count": len(expected), "langfuse_observation_count": len(observations),
                  "all_span_ids_received": expected <= {row["id"] for row in observations},
                  "synthetic_usage_only": True, "live_model_calls": 0,
                  "currency": "INR", "usd_to_inr": "94"}
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        (output / "observations.json").write_text(json.dumps(observations, indent=2) + "\n")
        print(json.dumps(report))
        return report["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    raise SystemExit(not verify(parser.parse_args().out))
