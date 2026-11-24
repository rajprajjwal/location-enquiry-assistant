"""Run the 80 pinned enquiries through orchestration using the live model."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from copilot.enquiry_interpretation import interpret
from copilot.model_gateway.client import LLMClient
from copilot.paths import REPO_ROOT
from copilot.enquiry_workflow import run_enquiry
from copilot.enquiry_workflow.retrieval import rag_document_search


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="New directory for verification results")
    args = parser.parse_args()
    source = REPO_ROOT / "eval/frozen-interpretation"
    manifest = json.loads((source / "manifest.json").read_text())
    data = (source / "inputs.jsonl").read_bytes()
    checksum = sha256(data).hexdigest()
    cases = [json.loads(line) for line in data.splitlines() if line.strip()]
    ids = [row["record_id"] for row in cases]
    if checksum != manifest["inputs_sha256"] or ids != manifest["frozen_record_ids"] or len(set(ids)) != 80:
        raise SystemExit("Frozen inputs do not match the manifest.")

    client = LLMClient()
    search = rag_document_search(mode="bm25", rerank=False)
    args.out.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    records = []
    with (args.out / "per-record.jsonl").open("w") as report:
        for index, row in enumerate(cases, 1):
            enquiry = {k: row[k] for k in ("query", "history", "known_facts")}
            try:
                output = interpret(enquiry, client=client)
                result = run_enquiry(enquiry, output, search=search, client=client)
                record = {
                    "record_id": row["record_id"], "status": result["status"],
                    "steps": result["step_count"], "critic": result["critic"]["verdict"],
                    "reason": result["critic"]["reason"], "has_draft": bool(result["response_draft"]),
                    "proposals": len(result["proposed_actions"]),
                    "actions": [step["action"] for step in result["steps"]],
                }
            except Exception as exc:
                record = {"record_id": row["record_id"], "status": "error", "error_type": type(exc).__name__}
            report.write(json.dumps(record) + "\n")
            report.flush()
            records.append(record)
            if index % 10 == 0:
                print(f"{index}/80 checked", flush=True)

    summary = {
        "started_at_utc": started, "inputs_sha256": checksum, "retrieval": "BM25",
        "records": len(records), "statuses": dict(Counter(item["status"] for item in records)),
        "critic_verdicts": dict(Counter(item.get("critic", "missing") for item in records)),
        "max_steps": max((item.get("steps", 0) for item in records), default=0),
        "over_step_limit": sum(item.get("steps", 0) > 10 for item in records),
        "all_ended_final_or_escalated": all(item["status"] in {"final", "escalated"} for item in records),
        "all_had_critic_review": all(item.get("critic") in {"pass", "needs_human"} for item in records),
        "scope": "Workflow and termination verification. Answer quality and retrieval ranking were not scored.",
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
