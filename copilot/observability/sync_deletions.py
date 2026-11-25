"""Submit queued Langfuse deletions after the local enquiry transaction commits."""
import argparse
from contextlib import closing
import os
from pathlib import Path
import re

import httpx

from copilot.case_storage.db import connect
from .storage import initialize
from .tracing import provider


def process_pending_deletions(con, *, limit=10):
    initialize(con)
    rows = list(con.execute("SELECT * FROM observability_trace_deletions WHERE status='pending' LIMIT ?", (limit,)))
    if not rows:
        return {"submitted": 0, "failed": 0}
    # Do not race queued exports against a remote deletion.
    if not provider().force_flush(timeout_millis=3000):
        return {"submitted": 0, "failed": len(rows)}
    submitted = failed = 0
    for row in rows:
        try:
            if not re.fullmatch(r"[0-9a-f]{32}", row["trace_id"]):
                raise ValueError("Invalid trace ID")
            if row["export_mode"] == "langfuse-local":
                from .langfuse_local import load_environment
                values = load_environment()
            else:
                values = os.environ
            with httpx.Client(base_url=values["LANGFUSE_BASE_URL"],
                              auth=(values["LANGFUSE_PUBLIC_KEY"], values["LANGFUSE_SECRET_KEY"]), timeout=3) as client:
                response = client.delete("/api/public/traces/" + row["trace_id"])
                if response.status_code != 404:
                    response.raise_for_status()
            with con:
                con.execute("UPDATE observability_trace_deletions SET status='submitted',attempts=attempts+1,last_error=NULL WHERE trace_id=?", (row["trace_id"],))
            submitted += 1
        except Exception as error:
            with con:
                con.execute("UPDATE observability_trace_deletions SET attempts=attempts+1,last_error=? WHERE trace_id=?", (type(error).__name__, row["trace_id"]))
            failed += 1
    return {"submitted": submitted, "failed": failed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    with closing(connect(args.db)) as connection:
        print(process_pending_deletions(connection))
