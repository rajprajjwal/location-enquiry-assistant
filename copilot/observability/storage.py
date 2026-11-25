"""Persist complete trace snapshots and query them without reading customer text."""
import json
import math


SCHEMA = """
CREATE TABLE IF NOT EXISTS observability_runs (
    trace_id TEXT PRIMARY KEY, started_ns INTEGER NOT NULL, ended_ns INTEGER,
    latency_ms REAL, record_id TEXT, run_id TEXT, bucket TEXT, api TEXT, team TEXT,
    split TEXT, case_id TEXT, outcome TEXT, input_tokens INTEGER, output_tokens INTEGER,
    embedding_tokens INTEGER, model_attempts INTEGER, embedding_attempts INTEGER,
    missing_usage_attempts INTEGER, cost_usd REAL, cost_status TEXT, summary_json TEXT NOT NULL, cost_inr REAL
);
CREATE TABLE IF NOT EXISTS observability_spans (
    span_id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, parent_span_id TEXT, name TEXT NOT NULL,
    kind TEXT NOT NULL, started_ns INTEGER NOT NULL, ended_ns INTEGER, latency_ms REAL,
    status TEXT NOT NULL, attributes_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observability_trace_deletions (
    trace_id TEXT PRIMARY KEY, export_mode TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT
);
CREATE INDEX IF NOT EXISTS observability_spans_trace ON observability_spans(trace_id);
CREATE INDEX IF NOT EXISTS observability_runs_bucket ON observability_runs(bucket, started_ns);
"""


def initialize(con):
    for statement in SCHEMA.split(";"):
        if statement.strip():
            con.execute(statement)
    if "cost_inr" not in {row["name"] for row in con.execute("PRAGMA table_info(observability_runs)")}:
        con.execute("ALTER TABLE observability_runs ADD COLUMN cost_inr REAL")


def save_run(con, run):
    spans = list(run.spans.values())
    root = next(row for row in spans if row["parent_span_id"] is None)
    info = run.summary
    metadata = run.metadata
    with con:
        initialize(con)
        legacy_table = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='traces'").fetchone()
        # An enquiry deleted by another connection must not be recreated here.
        if legacy_table and metadata.get("case_id") and not con.execute("SELECT 1 FROM traces WHERE id=?", (run.trace_id,)).fetchone():
            return
        con.execute(
            "INSERT OR REPLACE INTO observability_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run.trace_id, root["start_ns"], root["end_ns"], root["latency_ms"], metadata.get("record_id"),
             metadata.get("run_id"), metadata.get("bucket"), metadata.get("api"), metadata.get("team"),
             metadata.get("split", "live"), metadata.get("case_id"), metadata.get("status", "unknown"),
             info.get("input_tokens", 0), info.get("output_tokens", 0), info.get("embedding_tokens", 0),
             info.get("model_attempts", 0), info.get("embedding_attempts", 0), info.get("missing_usage_attempts", 0),
             float(info["cost_usd"]) if info.get("cost_usd") is not None else None,
             info.get("cost_status", "unpriced"), json.dumps(info, sort_keys=True),
             float(info["cost_inr"]) if info.get("cost_inr") is not None else None),
        )
        con.executemany(
            "INSERT OR REPLACE INTO observability_spans VALUES (?,?,?,?,?,?,?,?,?,?)",
            [(s["span_id"], run.trace_id, s["parent_span_id"], s["name"], s["attributes"]["copilot.span.kind"],
              s["start_ns"], s["end_ns"], s["latency_ms"], s["status"], json.dumps(s["attributes"], sort_keys=True))
             for s in spans],
        )
        if legacy_table:
            con.execute(
                "UPDATE traces SET model_calls=?, tokens_in=?, tokens_out=?, cost_usd=? WHERE id=?",
                (info.get("model_attempts", 0), info.get("input_tokens", 0), info.get("output_tokens", 0),
                 float(info["cost_usd"]) if info.get("cost_usd") is not None else None, run.trace_id),
            )


def list_runs(con, *, bucket=None, api=None, team=None, run_id=None, min_latency_ms=None,
              max_latency_ms=None, min_cost_inr=None, max_cost_inr=None, limit=100):
    initialize(con)
    clauses, values = [], []
    for column, value in (("bucket", bucket), ("api", api), ("team", team), ("run_id", run_id)):
        if value == "(unassigned)":
            clauses.append(f"{column} IS NULL")
        elif value is not None:
            clauses.append(f"{column}=?")
            values.append(value)
    for column, operator, value in (("latency_ms", ">=", min_latency_ms), ("latency_ms", "<=", max_latency_ms),
                                    ("cost_inr", ">=", min_cost_inr), ("cost_inr", "<=", max_cost_inr)):
        if value is not None:
            if not math.isfinite(float(value)) or value < 0:
                raise ValueError("Trace filters must be finite and nonnegative")
            clauses.append(f"{column}{operator}?")
            values.append(value)
    if type(limit) is not int or limit < -1:
        raise ValueError("Invalid trace limit")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    return [dict(r) for r in con.execute(
        "SELECT * FROM observability_runs" + where + " ORDER BY started_ns DESC LIMIT ?", (*values, limit),
    )]


def get_run(con, trace_id):
    initialize(con)
    row = con.execute("SELECT * FROM observability_runs WHERE trace_id=?", (trace_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["summary"] = json.loads(result.pop("summary_json"))
    result["spans"] = []
    for item in con.execute("SELECT * FROM observability_spans WHERE trace_id=? ORDER BY started_ns, span_id", (trace_id,)):
        span = dict(item)
        span["attributes"] = json.loads(span.pop("attributes_json"))
        result["spans"].append(span)
    return result


def delete_run(con, trace_id):
    initialize(con)
    row = con.execute("SELECT summary_json FROM observability_runs WHERE trace_id=?", (trace_id,)).fetchone()
    mode = json.loads(row["summary_json"]).get("export_mode", "local") if row else "local"
    if mode in {"langfuse", "langfuse-local"}:
        con.execute("INSERT OR IGNORE INTO observability_trace_deletions(trace_id,export_mode) VALUES (?,?)", (trace_id, mode))
    con.execute("DELETE FROM observability_spans WHERE trace_id=?", (trace_id,))
    con.execute("DELETE FROM observability_runs WHERE trace_id=?", (trace_id,))
