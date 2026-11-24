"""Activity 18 endpoint evidence from synthetic probes or the frozen inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .client import DEFAULT_MODEL, ConfigError, LLMClient


MODEL_CARD = {
    "model": DEFAULT_MODEL,
    "url": "https://huggingface.co/Qwen/Qwen3-8B",
    "total_parameters_billions": 8.2,
    "non_embedding_parameters_billions": 6.95,
    "strict_total_parameter_limit_pass": False,
    "project_model_accepted": True,
    "model_acceptance_basis": "Project owner confirmed use of the institute-provided model on 2026-11-20",
}
TOOL = {
    "type": "function",
    "function": {
        "name": "echo_value", "description": "Return the provided integer.",
        "parameters": {
            "type": "object", "properties": {"value": {"type": "integer"}},
            "required": ["value"], "additionalProperties": False,
        },
    },
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values, fraction):
    """Nearest-rank percentile of all completed calls, including failed checks."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(values) * fraction) - 1)]


def assert_probe(name, completion):
    if completion.model != DEFAULT_MODEL:
        raise ValueError("response model differs from configured model")
    if completion.finish_reason == "length":
        raise ValueError("completion reached the output limit")
    if name == "chat":
        if completion.text.strip() != "pong":
            raise ValueError("chat response must be pong")
    elif name == "json":
        if json.loads(completion.text) != {"status": "ok"}:
            raise ValueError("JSON response must contain status=ok")
    else:
        calls = completion.tool_calls
        if len(calls) != 1 or calls[0]["function"]["name"] != "echo_value" or not calls[0]["id"]:
            raise ValueError("expected one named function call with an ID")
        args = json.loads(calls[0]["function"]["arguments"])
        if args != {"value": 7} or type(args.get("value")) is not int:
            raise ValueError("tool arguments must contain integer value=7")


def smoke(client):
    results = []
    probes = (
        ("chat", "Reply with the single word pong.", {}),
        ("json", 'Return a JSON object with exactly one property, "status", equal to "ok".',
         {"response_format": {"type": "json_object"}}),
        ("tool", "Call echo_value with the integer value 7.",
         {"tools": [TOOL], "tool_choice": {"type": "function", "function": {"name": "echo_value"}}}),
    )
    for name, message, options in probes:
        record = {"probe": name, "passed": False}
        try:
            completion = client.complete(
                [{"role": "user", "content": message}], max_tokens=128, temperature=0, **options
            )
            record["response"] = asdict(completion)
            assert_probe(name, completion)
            record["passed"] = True
        except Exception as error:
            record["error"] = str(error)
            record["error_type"] = type(error).__name__
        results.append(record)
    return results


def frozen(client, directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    inputs_path = directory / "inputs.jsonl"
    if sha(inputs_path) != manifest["inputs_sha256"]:
        raise ValueError("frozen input hash differs from the manifest")
    records = [json.loads(line) for line in inputs_path.read_text().splitlines() if line.strip()]
    ids = [record["record_id"] for record in records]
    if ids != manifest["frozen_record_ids"] or len(ids) != len(set(ids)) or len(ids) != 80:
        raise ValueError("expected the manifest's 80 unique frozen records in order")
    results = []
    for index, record in enumerate(records, 1):
        item = {"record_id": record["record_id"], "passed": False}
        messages = [{"role": "system", "content":
                     "Draft a concise response to the location API enquiry. State uncertainty when details are unknown."}]
        messages.extend({"role": turn["role"], "content": turn["text"]} for turn in record.get("history", []))
        messages.append({"role": "user", "content": record["query"]})
        try:
            completion = client.complete(messages, max_tokens=512, temperature=0)
            item["response"] = asdict(completion)
            item["passed"] = bool(completion.text.strip()) and completion.model == DEFAULT_MODEL and completion.finish_reason != "length"
        except Exception as error:
            item["error"] = str(error)
            item["error_type"] = type(error).__name__
        results.append(item)
        print(f"Completed {index}/{len(records)} frozen endpoint calls", flush=True)
    return results, sha(directory / "manifest.json"), sha(inputs_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="new directory for this run")
    parser.add_argument("--frozen-dir", type=Path, help="also send the frozen enquiries to the endpoint")
    args = parser.parse_args()
    # Fail before a model call when the output location cannot be used.
    client = LLMClient()
    args.out.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    smoke_results = smoke(client)
    frozen_results = []
    manifest_sha = inputs_sha = None
    smoke_passed = all(item["passed"] for item in smoke_results)
    if args.frozen_dir and smoke_passed:
        frozen_results, manifest_sha, inputs_sha = frozen(client, args.frozen_dir)
    measured = frozen_results if frozen_results else smoke_results
    timings = [item["response"]["latency_ms"] for item in measured if "response" in item]
    report = {
        "started_at_utc": started, "model_card": MODEL_CARD,
        "smoke_passed": smoke_passed, "smoke": smoke_results,
        "frozen_requested": args.frozen_dir is not None,
        "frozen_records": len(frozen_results),
        "frozen_successes": sum(item["passed"] for item in frozen_results),
        "manifest_sha256": manifest_sha, "inputs_sha256": inputs_sha,
        "latency_population": "frozen endpoint completions" if frozen_results else "synthetic smoke completions",
        "latency_samples": len(timings),
        "latency_p50_ms": percentile(timings, 0.50),
        "latency_p95_ms": percentile(timings, 0.95),
        "activity18_passed": smoke_passed and len(frozen_results) == 80
            and all(item["passed"] for item in frozen_results)
            and (MODEL_CARD["strict_total_parameter_limit_pass"] or MODEL_CARD["project_model_accepted"]),
    }
    (args.out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if frozen_results:
        (args.out / "responses.jsonl").write_text(
            "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in frozen_results)
        )
    print(json.dumps({key: report[key] for key in (
        "smoke_passed", "frozen_records", "latency_p50_ms", "latency_p95_ms", "activity18_passed"
    )}))
    return 0 if report["activity18_passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConfigError as error:
        raise SystemExit(str(error))
