"""Verify live trace completeness and optional replay parity without scoring answers."""
import argparse
from collections import Counter
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time

import httpx
from openai.types.chat import ChatCompletion

from copilot.case_storage import cases
from copilot.case_storage.db import connect
from copilot.enquiry_workflow.cases import run_case
from copilot.enquiry_workflow.retrieval import rag_document_search, warm_retrieval_runtime
from copilot.model_gateway.client import LLMClient
from copilot.model_gateway.reliability import query_session
from copilot.observability.langfuse_local import load_environment
from copilot.observability.storage import get_run
from copilot.observability.tracing import provider, trace_run
from .langfuse_smoke import fetch_observations


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class RecordingClient(LLMClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def _once(self, messages, max_tokens, temperature, extra):
        item = {"request_hash": digest([messages, max_tokens, temperature, extra])}
        started = time.monotonic()
        try:
            response = super()._once(messages, max_tokens, temperature, extra)
            item["response"] = response.model_dump()
            return response
        except Exception as error:
            item.update(error_type=type(error).__name__, status_code=getattr(error, "status_code", None))
            raise
        finally:
            item["elapsed_seconds"] = time.monotonic() - started
            self.records.append(item)


class ReplayClient(LLMClient):
    def __init__(self, records, clock):
        super().__init__(api_key="synthetic-replay", ca_cert=__file__)
        self.records, self.clock, self.position, self.mismatches = records, clock, 0, []

    def _once(self, messages, max_tokens, temperature, extra):
        if self.position >= len(self.records):
            self.mismatches.append("unexpected_request")
            raise RuntimeError("Replay exhausted")
        item = self.records[self.position]
        self.position += 1
        if item["request_hash"] != digest([messages, max_tokens, temperature, extra]):
            self.mismatches.append("request_hash_changed")
            raise RuntimeError("Replay request changed")
        self.clock.advance(item["elapsed_seconds"])
        if "error_type" in item:
            error = type(item["error_type"], (Exception,), {})("Replayed transport failure")
            error.status_code = item["status_code"]
            raise error
        return ChatCompletion.model_validate(item["response"])


class Clock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def seeded_case(con, row):
    context = row["input"]
    if context.get("known_facts"):
        raise ValueError("This verifier requires the approved inputs with empty initial known facts")
    identifier = cases.create_case(con, customer=row["record_id"])
    for turn in context.get("history", []):
        cases.add_message(con, identifier, turn["role"], turn["text"])
    return identifier


def projection(con, result):
    state = cases.load_state(con, result["case_id"])
    return {**{key: result.get(key) for key in (
        "status", "outputs", "clarifying_questions", "proposed_actions", "critic", "step_count",
    )}, "steps": [{k: s.get(k) for k in ("action", "status")} for s in result["steps"]],
            "pending_clarification": state.get("pending_clarification"),
            "pending_provider_question": state.get("pending_provider_question"),
            "pending_approvals": [{"type": a["type"], "payload": a["payload"], "status": a["status"]}
                                  for a in cases.list_pending(con, result["case_id"])]}


def verify(inputs, output, *, parity=False, retrieval="bm25"):
    rows = [json.loads(line) for line in inputs.read_text().splitlines() if line.strip()]
    ids = [row["record_id"] for row in rows]
    if len(ids) != len(set(ids)) or any(row["split"] not in {"working_eval", "frozen"} for row in rows):
        raise ValueError("Expected unique working-eval or frozen records; holdout is prohibited")
    if parity and any(row["split"] != "working_eval" for row in rows):
        raise ValueError("Replay parity is restricted to working-eval")
    if not rows:
        raise ValueError("Empty trace verification inputs")
    if any(row["split"] == "frozen" for row in rows):
        from .prepare_frozen import validate
        validate(rows)
    output.mkdir(parents=True, exist_ok=False)
    os.environ["COPILOT_TRACE_EXPORT"] = "langfuse-local"
    values = load_environment()
    search = rag_document_search(mode=retrieval, rerank=retrieval == "hybrid")
    if retrieval == "hybrid":
        warm_retrieval_runtime()
    results = []
    with closing(connect(output / "traces.db")) as con, httpx.Client(
        base_url=values["LANGFUSE_BASE_URL"], auth=(values["LANGFUSE_PUBLIC_KEY"], values["LANGFUSE_SECRET_KEY"]),
        timeout=30,
    ) as remote, (output / "per-record.jsonl").open("w") as record_file:
        for index, row in enumerate(rows, 1):
            case_id = seeded_case(con, row)
            client = RecordingClient()
            metadata = {key: row[key] for key in ("record_id", "bucket", "api", "team", "split")}
            with trace_run(connection=con, metadata={**metadata, "run_id": output.name}) as run:
                result = run_case(con, row["input"]["query"], case_id=case_id, client=client, search=search)
            trace = get_run(con, run.trace_id)
            local_ids = {span["span_id"] for span in trace["spans"]}
            step_indices = sorted(span["attributes"]["copilot.step.index"] for span in trace["spans"]
                                  if span["kind"] == "workflow_step")
            record = {"record_id": row["record_id"], "bucket": row["bucket"], "api": row["api"],
                      "trace_id": run.trace_id, "status": result["status"],
                      "step_count": result["step_count"], "span_count": len(local_ids),
                      "step_spans_complete": step_indices == list(range(1, result["step_count"] + 1)),
                      "model_attempts_match": trace["model_attempts"] == result["reliability"]["model_attempts"],
                      "tool_spans_match": sum(s["kind"] == "tool" for s in trace["spans"]) == len(result["tool_calls"]),
                      "usage": trace["summary"], "latency_ms": trace["latency_ms"]}
            if parity:
                baseline = projection(con, result)
                clock = Clock()
                replay = ReplayClient(client.records, clock)
                old = os.environ.get("COPILOT_TRACING_ENABLED")
                os.environ["COPILOT_TRACING_ENABLED"] = "0"
                try:
                    with TemporaryDirectory(prefix="trace-parity-") as temp, closing(connect(Path(temp) / "baseline.db")) as baseline_con:
                        replay_id = seeded_case(baseline_con, row)
                        with query_session(clock=clock, sleeper=clock.advance):
                            untraced = run_case(baseline_con, row["input"]["query"], case_id=replay_id, client=replay, search=search)
                        comparison = projection(baseline_con, untraced)
                    record.update(business_outputs_unchanged=baseline == comparison,
                                  replay_requests_match=not replay.mismatches and replay.position == len(client.records),
                                  traced_projection_sha256=digest(baseline), untraced_projection_sha256=digest(comparison),
                                  replay_mode="Same recorded model replies; simulated endpoint latency; no replay endpoint calls")
                finally:
                    if old is None:
                        os.environ.pop("COPILOT_TRACING_ENABLED", None)
                    else:
                        os.environ["COPILOT_TRACING_ENABLED"] = old
            provider().force_flush(timeout_millis=10000)
            received = []
            for _ in range(12):
                received = fetch_observations(remote, run.trace_id)
                if local_ids <= {span["id"] for span in received}:
                    break
                time.sleep(2)
            record["langfuse_spans_complete"] = local_ids <= {span["id"] for span in received}
            record["langfuse_span_count"] = len(received)
            checks = ("step_spans_complete", "model_attempts_match", "tool_spans_match", "langfuse_spans_complete")
            record["passed"] = all(record[key] for key in checks) and (not parity or (
                record["business_outputs_unchanged"] and record["replay_requests_match"]))
            results.append(record)
            record_file.write(json.dumps(record) + "\n")
            record_file.flush()
            print(f"{index}/{len(rows)}: {row['record_id']} trace={'pass' if record['passed'] else 'FAIL'}", flush=True)
    summary = {"records": len(results), "passed": sum(r["passed"] for r in results),
               "all_passed": all(r["passed"] for r in results), "retrieval": retrieval,
               "inputs_sha256": sha256(inputs.read_bytes()).hexdigest(),
               "local_step_span_coverage": sum(r["step_spans_complete"] for r in results) / len(results),
               "langfuse_span_coverage": sum(r["langfuse_spans_complete"] for r in results) / len(results),
               "statuses": dict(Counter(r["status"] for r in results)),
               "cost_statuses": dict(Counter(r["usage"]["cost_status"] for r in results)),
               "business_changes": sum(not r.get("business_outputs_unchanged", True) for r in results),
               "holdout_selected": 0, "answer_quality_scored": False, "currency": "INR", "usd_to_inr": "94"}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    return summary["all_passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--parity", action="store_true")
    parser.add_argument("--retrieval", choices=("bm25", "hybrid"), default="bm25")
    args = parser.parse_args()
    raise SystemExit(not verify(args.inputs, args.out, parity=args.parity, retrieval=args.retrieval))
