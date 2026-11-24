"""Run synthetic reliability faults without endpoint calls or evaluation data."""
import argparse
from contextlib import closing
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace

from copilot.case_storage.db import connect
from copilot.case_storage import cases, traces
from copilot.enquiry_workflow.cases import run_case
from copilot.model_gateway.client import LLMClient
from copilot.model_gateway.reliability import Limits, query_session
from copilot.model_gateway.token_counting import count_prompt, count_text
from copilot.registered_tools.tool_registry import DocumentSearchTool
from copilot.response_drafting.schemas import validate_outputs


class Clock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def interpretation_json():
    fields = ("use_case", "region", "monthly_volume", "current_provider", "timeline",
              "budget", "technical_constraints", "decision_maker")
    return json.dumps({
        "intent": "docs_how_to", "sub_intent": "parameter_question", "api": "directions",
        "team": "Support", "confidence": {"intent": .4, "api": .7, "team": .5},
        "qualification": {key: {"value": None, "evidence": None} for key in fields},
    })


class FaultClient(LLMClient):
    """Inject below the shared client so retry and budget controls remain active."""
    def __init__(self, mode, clock):
        super().__init__(api_key="synthetic-key", ca_cert=__file__)
        self.mode, self.clock, self.calls = mode, clock, 0

    def _once(self, messages, max_tokens, temperature, extra):
        self.calls += 1
        if self.mode == "persistent_model_timeout" or (
                self.mode == "transient_model_timeout" and self.calls == 1):
            raise TimeoutError("Injected model timeout")
        if self.mode == "query_deadline":
            self.clock.advance(121)
        if self.mode == "persistent_invalid_json" or (
                self.mode == "transient_invalid_json" and self.calls == 1):
            text = "{"
        elif max_tokens == 512:
            text = interpretation_json()
        elif max_tokens == 600:
            text = '{"questions": []}'
        else:
            text = '{"passage": 1, "answers_enquiry": true}'
        prompt = count_prompt(messages, tools=extra.get("tools"))
        completion = count_text(text)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=[]), finish_reason="stop")],
            model="synthetic-Qwen3-8B", usage=SimpleNamespace(
                prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion),
        )


MODES = (
    "transient_model_timeout", "persistent_model_timeout", "transient_invalid_json",
    "persistent_invalid_json", "transient_tool_error", "persistent_tool_error",
    "invalid_tool_output", "token_budget", "query_deadline", "tool_timeout",
)
RECOVERABLE = {"transient_model_timeout", "transient_invalid_json", "transient_tool_error"}


def run_scenario(mode, variation, folder):
    clock = Clock()
    client = FaultClient(mode, clock)
    searches = 0
    def search(query):
        nonlocal searches
        searches += 1
        if mode == "persistent_tool_error" or (mode == "transient_tool_error" and searches == 1):
            raise RuntimeError("Injected search failure")
        if mode == "tool_timeout":
            time.sleep(.08)
        return [{"source_url": "https://example.test/directions",
                 "relevant_passage": "Add intermediate locations in the waypoints field."}]

    tool = DocumentSearchTool(search_function=search)
    if mode == "invalid_tool_output":
        definition = replace(tool.tool_definition(), executor=lambda _: {"results": "invalid"})
        tool.tool_definition = lambda: definition
    limits = Limits(token_budget=1) if mode == "token_budget" else Limits()
    if mode == "tool_timeout":
        limits = limits.model_copy(update={"tool_timeout_seconds": .01})
    question = [
        "How do I set waypoints in Mapbox Directions?",
        "How can I add intermediate waypoints in the Mapbox Directions API?",
        "In Mapbox Directions, how do I include waypoints?",
        "How are waypoints passed to Mapbox Directions?",
        "Please explain setting intermediate waypoints for Mapbox Directions.",
    ][variation]
    with query_session(limits, clock=clock, sleeper=clock.advance) as session:
        with closing(connect(folder / f"{mode}-{variation}.db")) as con:
            result = run_case(con, question, client=client, search=tool, diagnostic_planning=False)
            stored = traces.get_trace(con, result["trace_id"])
            # Safe fallbacks remain drafts; nothing is sent or applied automatically.
            decisions = cases.decision_log(con)
            actions = result["proposed_actions"]
            schema_errors = validate_outputs(result["outputs"])
            reliability = session.snapshot()
    expected = "final" if mode in RECOVERABLE else "escalated"
    errors = []
    if result["status"] != expected:
        errors.append(f"Expected {expected}, got {result['status']}")
    if schema_errors:
        errors.append("Output schema failed")
    if decisions or any(action.get("executed") for action in actions):
        errors.append("Unapproved action executed")
    if max(reliability["retries_by_step"].values(), default=0) > 2:
        errors.append("Retry limit exceeded")
    if reliability["reserved_tokens"] > limits.token_budget:
        errors.append("Token reservation exceeded budget")
    if reliability["observed_tokens"] > reliability["reserved_tokens"]:
        errors.append("Observed usage exceeded reservation")
    if not stored:
        errors.append("Trace not persisted")
    return {"id": f"{mode}-{variation + 1}", "fault": mode, "expected": expected,
            "status": result["status"], "passed": not errors, "errors": errors,
            "schema_valid": not schema_errors, "model_calls": client.calls, "search_attempts": searches,
            "proposed_actions": len(actions), "decisions_applied": len(decisions),
            "critic": result["critic"], "reliability": reliability}


def verify(output):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="copilot-reliability-") as temporary:
        records = [run_scenario(mode, variation, Path(temporary)) for mode in MODES for variation in range(5)]
    (output / "faults.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records))
    failures = sum(not row["passed"] for row in records)
    summary = {
        "runs": len(records), "passed": len(records) - failures, "failures": failures,
        "task_failure_rate": failures / len(records),
        "recovered_answers": sum(row["passed"] and row["expected"] == "final" for row in records),
        "expected_safe_fallbacks": sum(row["passed"] and row["expected"] == "escalated" for row in records),
        "schema_valid": sum(row["schema_valid"] for row in records),
        "max_retries_per_step": max(max(row["reliability"]["retries_by_step"].values(), default=0) for row in records),
        "budget_overruns": sum(row["reliability"]["reserved_tokens"] > row["reliability"]["limits"]["token_budget"] for row in records),
        "unapproved_decisions": sum(row["decisions_applied"] for row in records),
        "evaluation_data_used": False, "network_calls": 0,
        "diagnostic_planning": False,
        "acceptance_met": failures == 0,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if verify(args.output)["acceptance_met"] else 1)
