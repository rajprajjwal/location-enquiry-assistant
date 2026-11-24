from dataclasses import replace
import json

from jsonschema import Draft202012Validator
import pytest

from copilot.registered_tools.tool_registry import ComparisonTool, DocumentSearchTool, SandboxRecordUpdateTool, ToolRegistry


@pytest.mark.parametrize(("tool", "valid_input", "bad_output"), [
    (DocumentSearchTool().tool_definition(), {"query": "walking"}, {"results": [{"source_url": "https://example.test"}]}),
    (ComparisonTool(lambda _: {}).tool_definition(),
     {"api": "directions", "monthly_usage": 500, "provider_plans": {}},
     {"requested_api": "directions", "providers": "Example"}),
    (SandboxRecordUpdateTool().tool_definition(),
     {"record_id": "TKT-123", "field_name": "status", "previous_value": None,
      "proposed_value": "In progress", "reason": "Customer confirmed"},
     {"record_id": "TKT-123", "approval_status": "approved"}),
])
def test_registered_tools_reject_bad_results(tool, valid_input, bad_output):
    registry = ToolRegistry()
    registry.register(replace(tool, executor=lambda _: bad_output))
    Draft202012Validator.check_schema(tool.input_schema)
    Draft202012Validator.check_schema(tool.output_schema)
    with pytest.raises(ValueError, match="Output validation failed"):
        registry.execute(tool.name, valid_input)
    entry, = registry.execution_log
    assert entry["input_validation"] == "passed"
    assert entry["output_validation"] == entry["validation_result"] == "failed"
    assert entry["execution_status"] == "error"
    assert "Customer confirmed" not in json.dumps(entry)


def _openai_call(name, arguments):
    return {"id": "call_12", "type": "function", "function": {"name": name, "arguments": arguments}}


def test_openai_function_dispatch_preserves_id_and_logs_rejections():
    seen = []
    registry = ToolRegistry()
    registry.register(DocumentSearchTool(search_function=lambda q: seen.append(q) or []).tool_definition())
    spec, = registry.function_specs()
    assert spec["function"]["parameters"]["required"] == ["query"]
    call = _openai_call("document_search", '{"query": "private search text"}')
    message = registry.execute_openai_call(call)
    assert message["role"] == "tool" and message["tool_call_id"] == "call_12"
    assert json.loads(message["content"]) == {"results": []}
    with pytest.raises(ValueError, match="Input validation failed"):
        registry.execute_openai_call(_openai_call("document_search", '{"query": 7}'))
    with pytest.raises(ValueError, match="Input validation failed"):
        registry.execute_openai_call(_openai_call("document_search", '{"query":'))
    with pytest.raises(KeyError):
        registry.execute_openai_call(_openai_call("unregistered", "{}"))
    assert seen == ["private search text"]
    log = registry.execution_log
    assert [row["execution_status"] for row in log] == ["success", "rejected", "rejected", "rejected"]
    assert [row["registered"] for row in log] == [True, True, True, False]
    assert "private search text" not in json.dumps(log)
