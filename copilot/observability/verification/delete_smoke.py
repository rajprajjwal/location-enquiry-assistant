"""Delete an ingested synthetic trace and distinguish submission from removal."""
import argparse
from contextlib import closing
import json
from pathlib import Path

import httpx

from copilot.case_storage.db import connect
from copilot.observability.langfuse_local import load_environment
from copilot.observability.storage import delete_run, get_run
from copilot.observability.sync_deletions import process_pending_deletions
from .langfuse_smoke import fetch_observations


def verify(smoke, output):
    trace_id = json.loads((smoke / "report.json").read_text())["trace_id"]
    with closing(connect(smoke / "smoke.db")) as con:
        with con:
            delete_run(con, trace_id)
        result = process_pending_deletions(con)
        queue = con.execute("SELECT status FROM observability_trace_deletions WHERE trace_id=?", (trace_id,)).fetchone()
        local_removed = get_run(con, trace_id) is None
    values = load_environment()
    with httpx.Client(base_url=values["LANGFUSE_BASE_URL"],
                      auth=(values["LANGFUSE_PUBLIC_KEY"], values["LANGFUSE_SECRET_KEY"]), timeout=30) as remote:
        remaining = fetch_observations(remote, trace_id)
    report = {"trace_id": trace_id, "local_removed": local_removed, "queue_status": queue[0],
              "submission": result, "remote_removal_confirmed": not remaining,
              "remote_remaining_spans": len(remaining), "synthetic_only": True, "live_model_calls": 0}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    verify(args.smoke, args.out)
