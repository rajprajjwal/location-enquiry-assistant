import json
from pathlib import Path
from unittest.mock import create_autospec

import pytest

from copilot.model_gateway.client import LLMClient
from copilot.enquiry_workflow.cases import run_case
from tests.support.helpers import completion, model_json


def test_streamlit_draft_escalation_and_approval(tmp_path, monkeypatch):
    testing = pytest.importorskip("streamlit.testing.v1")
    client = create_autospec(LLMClient, instance=True)

    def reply(messages, **options):
        if "response_format" in options:
            payload = json.loads(messages[-1]["content"])
            if payload.get("qualification_plan"):
                return completion(json.dumps({"supplied_facts": [], "groups": [],
                    "reason": "The waypoint configuration question is answered by documentation."}))
            if payload.get("diagnostic_plan"):
                return completion(json.dumps({
                    "decision": "request_reproduction" if "503" in payload["enquiry"] else "none",
                    "reason": "Inspect a failing request." if "503" in payload["enquiry"] else "Provider clarification is active.",
                }))
            if "active_question" in payload:
                return completion(json.dumps({"questions": [
                    {"field": "peak_request_rate", "text": "What was the peak request rate?",
                     "facts": ["peak_request_rate"], "decision_impact": "Check for an overload.",
                     "evidence": payload["enquiry"]}
                ]}))
            if "candidate" in payload:
                return completion('{"answers_enquiry": true}')
            passages = payload["passages"]
            index = next(
                i for i, hit in enumerate(passages, 1) if "waypoint" in hit["relevant_passage"].lower()
            )
            return completion(json.dumps({"passage": index}))
        incident = "503" in messages[-1]["content"]
        return completion(model_json(
            intent="troubleshooting" if incident else "docs_how_to",
            sub_intent="production_incident" if incident else "parameter_question",
            api="directions", team="Support",
        ))

    client.complete.side_effect = reply
    monkeypatch.setattr("copilot.case_storage.db.DB_PATH", tmp_path / "review.db")
    monkeypatch.setattr(
        "copilot.enquiry_workflow.cases.run_case",
        lambda *args, **kwargs: run_case(*args, client=client, **kwargs),
    )
    monkeypatch.setattr(
        "copilot.enquiry_workflow.retrieval.retrieval_setup_issues",
        lambda *args, **kwargs: ["Build the dense index."],
    )
    app_path = Path(__file__).resolve().parents[2] / "copilot/streamlit_ui/streamlit_app.py"
    app = testing.AppTest.from_file(str(app_path)).run()
    assert not app.exception
    app.radio[0].set_value("Hybrid with reranking").run()
    assert any("Build the dense index." in item.value for item in app.warning)
    assert next(button for button in app.button if button.label == "Run enquiry").disabled
    client.complete.assert_not_called()
    app.radio[0].set_value("BM25").run()

    def submit(query):
        app.text_area[0].set_value(query)
        next(button for button in app.button if button.label == "Run enquiry").click().run()
        assert not app.exception

    app.text_input[0].set_value("Customer A")
    submit("How do I set waypoints in the Directions API?")
    assert any("Which map provider are you using?" in item.value for item in app.markdown)
    assert app.text_area[0].value == ""
    first_case = app.selectbox(key="selected_case").value
    assert first_case is not None
    assert any("Assistant: Which map provider" in message.value for message in app.text)

    app.selectbox(key="selected_case").select_index(0).run()
    app.text_input[0].set_value("Customer B")
    submit("Production is down. Directions returns 503 for all requests.")
    second_case = app.selectbox(key="selected_case").value
    assert second_case != first_case
    assert any("pending human review" in info.value for info in app.info)
    assert any(item.label == "Suggested follow-up questions" for item in app.expander)
    assert not any("Enter the customer’s reply" in caption.value for caption in app.caption)
    next(button for button in app.button if button.label == "Approve").click().run()
    assert not app.exception
    assert any("approved" in item.value for item in app.json)
    assert any(item.label == "outcome" for item in app.expander)

    reopened = testing.AppTest.from_file(str(app_path)).run()
    picker = reopened.selectbox(key="selected_case")
    customer_a = next(index for index, label in enumerate(picker.options) if label.startswith("Customer A"))
    assert any(label.startswith("Customer B") for label in picker.options)
    picker.select_index(customer_a).run()
    app = reopened
    assert app.selectbox(key="selected_case").value == first_case
    assert any("Customer: How do I set waypoints" in message.value for message in app.text)
    assert any("Assistant: Which map provider" in message.value for message in app.text)
    assert not any(message.value.startswith("Customer: Production is down") for message in app.text)
    submit("Mapbox")
    assert any("Critic verdict: pass" in caption.value for caption in app.caption)
    assert app.text_area[0].value == ""

    next(control for control in app.selectbox if control.label == "Run").select_index(0).run()
    delete_button = next(button for button in app.button if button.label == "Delete enquiry and traces")
    assert delete_button.disabled
    next(box for box in app.checkbox if box.label.startswith("Permanently delete")).check().run()
    next(button for button in app.button if button.label == "Delete enquiry and traces").click().run()
    assert not app.exception
    assert any("Enquiry and local traces deleted. Langfuse deletion is tracked separately." == item.value for item in app.success)
    assert not any(message.value == "Customer: Mapbox" for message in app.text)
    assert any("Customer: How do I set waypoints" in message.value for message in app.text)
    assert any("approved" in item.value for item in app.json)

    runs = next(control for control in app.selectbox if control.label == "Run")
    incident = next(i for i, label in enumerate(runs.options) if second_case in label)
    runs.select_index(incident).run()
    next(box for box in app.checkbox if box.label.startswith("Permanently delete")).check().run()
    next(button for button in app.button if button.label == "Delete enquiry and traces").click().run()
    assert not app.exception
    assert any("Source enquiry deleted" in caption.value for caption in app.caption)
    assert any('"decision": "approved"' in item.value for item in app.json)
