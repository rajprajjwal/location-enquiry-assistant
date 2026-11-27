"""Connect the Activity 19 workflow to the local case and approval store."""

import json
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from copilot.enquiry_interpretation import interpret, rules
from copilot.observability.tracing import traced_case, current_run, tag_run, observed_span, record_trace_io
from copilot.response_drafting.follow_up_questions import add_follow_up_questions

from .approval_sources import backfill_approval_sources
from .case_memory import interpretation_facts, load_conversation, turn_event
from .providers import bind_confirmed_provider, provider_reply
from .ownership_status import customer_status_reply
from .sandbox_updates import record_target
from .workflow import run_enquiry
from copilot.model_gateway.reliability import query_scope, active_query


@traced_case
@query_scope("case", attach=True)
def run_case(con, query, *, case_id=None, customer=None, client=None, search=None, diagnostic_planning=True, confirmed_customer_status=None):
    """Run and record a case turn. Return pending actions for the review queue."""
    from copilot.case_storage import sandbox
    from copilot.safety.pii import redact
    from copilot.case_storage import cases

    if confirmed_customer_status not in {None, "existing", "new"}:
        raise ValueError("Confirmed customer status must be existing or new.")
    query = redact(query.strip())
    if not query:
        raise ValueError("Enter an enquiry.")
    if case_id is not None and cases.get_case(con, case_id) is None:
        raise ValueError("Case does not exist.")
    # Prior drafts are retained for review and count as history only after sending.
    history = [
        {"role": "assistant" if message["role"] == "clarification" else message["role"], "text": message["content"]}
        for message in cases.get_case_history(con, case_id) if message["role"] in {"user", "assistant", "clarification"}
    ] if case_id else []
    state = cases.load_state(con, case_id) if case_id else {}
    conversation = load_conversation(con, case_id) if case_id else None
    saved_ownership = conversation.ownership_status if conversation else {}
    record_status = cases.known_facts(con, case_id).get("customer_status") if case_id else None
    effective_status = confirmed_customer_status or saved_ownership.get("customer_status") or record_status
    # Saved uncertainty must not hide a verified account fact.
    if effective_status == "unknown" and not saved_ownership.get("status_deferred"):
        effective_status = record_status
    pending = state.get("pending_clarification")
    if pending is None and state.get("pending_provider_question"):
        pending = {"field": "provider", "task": state["pending_provider_question"]}
    task = query
    confirmed_field = None
    confirmed_provider = None
    ownership_query = None
    if pending and pending['field'] == 'customer_status':
        question = history[-1]['text'] if history and history[-1]['role'] == 'assistant' else ''
        status_reply = customer_status_reply(query, question, bound=True)
        if status_reply is not None:
            effective_status = status_reply
            task = pending['task']
            ownership_query = query
            confirmed_field = 'customer_status'
    elif pending and pending["field"] in {"provider", "current_provider"}:
        provider = provider_reply(query)
        if provider:
            task = f"{pending['task']} Provider: {provider}."
            confirmed_field = "current_provider"
            confirmed_provider = provider
    elif pending and len(query) <= 180 and "?" not in query and not rules.is_decline_value(query):
        task = f"{pending['task']} Customer confirmed {pending['field'].replace('_', ' ')}: {query}."
        confirmed_field = pending["field"]
    known = interpretation_facts(conversation)
    if confirmed_provider:
        # Both pending aliases answer the same stored customer fact.
        known = [fact for fact in known if fact["field"] != "current_provider"]
        known.append({"field": "current_provider", "value": confirmed_provider, "source": "history"})
    enquiry = {"query": task, "history": history, "known_facts": known}
    started = perf_counter()
    shared = None
    if diagnostic_planning:
        from copilot.diagnostics.facts import build_diagnostic_state
        shared = build_diagnostic_state(
            {"query": query, "history": history, "known_facts": enquiry["known_facts"]},
            conversation.diagnostic_state if conversation else None,
        )
        shared.completed_checks = list(dict.fromkeys([
            *(conversation.diagnostic_history if conversation else []), *turn_event(query)["diagnostics"],
        ]))
    interpretation = (interpret(enquiry, client=client, diagnostics=shared.model_dump(mode="json"))
                      if shared is not None else interpret(enquiry, client=client))
    if confirmed_provider:
        interpretation = bind_confirmed_provider(interpretation, confirmed_provider)
    capture = current_run()
    if capture:
        tag_run(api=capture.metadata.get("api") or interpretation.api, team=capture.metadata.get("team") or interpretation.team)
    target = record_target(task)
    result = run_enquiry(
        enquiry, interpretation, search=search, client=client,
        record_snapshot=sandbox.get(con, target) if target else None,
        confirmed_customer_status=effective_status,
        confirmed_provider=confirmed_provider,
        ownership_query=ownership_query,
    )
    if shared is not None:
        result = {**result, "diagnostic_context": {
            "state": shared.model_dump(mode="json"), "retrieved_evidence": result.get("retrieved_evidence", []),
            "interpretation": {"api": interpretation.api, "intent": interpretation.intent},
            "pricing_requirements": result.get("pricing_requirements", {}),
        }}
    result = add_follow_up_questions(result, enquiry, client=client)
    from copilot.qualification.finalization import finalize_requirements
    result = finalize_requirements(result, enquiry)
    from copilot.response_drafting.customer_response import format_customer_response
    result = {**result, 'customer_response': format_customer_response(result)}
    # Root observation: the redacted customer turn in, the customer-facing reply out.
    record_trace_io(input=query, output=result['customer_response']['markdown'])
    if shared is not None:
        from copilot.diagnostics.facts import DiagnosticQuestion, DiagnosticState
        shared = DiagnosticState.model_validate(result["diagnostic_context"]["state"])
        for question in result["clarifying_questions"]["questions"]:
            field = "provider" if question.get("field") == "current_provider" else question.get("field")
            asked = DiagnosticQuestion(facts=[field] if field else [], text=question["text"], status="asked")
            if asked not in shared.questions:
                shared.questions.append(asked)
        result["diagnostic_context"]["state"] = shared.model_dump(mode="json")
    if case_id is None:
        case_id = cases.create_case(
            con, customer=redact((customer or "").strip()) or "unknown",
            workflow=(interpretation.team or "Support").lower(),
            api=interpretation.api, category=interpretation.intent,
        )
    if result["proposed_actions"]:
        with con:
            backfill_approval_sources(con, case_id)
    trace_id = current_run().trace_id if current_run() else uuid4().hex
    cases.add_message(con, case_id, "user", query, turn_trace_id=trace_id)
    for question in result["clarifying_questions"]["questions"]:
        cases.add_message(con, case_id, "clarification", question["text"], turn_trace_id=trace_id)
    draft = result["response_draft"]
    if draft:
        cases.add_message(con, case_id, "draft", draft["draft_text"], turn_trace_id=trace_id)
    for proposal in result["proposed_actions"]:
        if proposal["action_type"] == "propose_escalation":
            payload = proposal["escalation"]
            existing = next((
                action for action in cases.list_pending(con, case_id)
                if action["type"] == "escalation"
                and action["payload"]["owner"] == payload["owner"]
                and con.execute(
                    "SELECT 1 FROM approval_enquiry_sources WHERE action_id = ? AND deleted_at IS NULL",
                    (action["id"],),
                ).fetchone()
            ), None)
            if existing:
                cases.update_pending_payload(
                    con, existing["id"], payload, actor="orchestrator", source_trace_id=trace_id,
                )
            else:
                cases.request_approval(
                    con, case_id, "escalation", payload, requested_by="orchestrator", source_trace_id=trace_id,
                )
        elif proposal["action_type"] == "propose_record_update":
            cases.request_approval(
                con, case_id, "record_update", proposal["record_update"],
                requested_by="orchestrator", source_trace_id=trace_id,
            )
    interpreted = interpretation.model_dump(mode="json")
    qualification = interpreted["qualification_details"]
    provenance = interpreted["field_provenance"]
    facts = {
        field: value for field, value in qualification.items()
        if value is not None and field not in {"complete", "missing_required_fields"}
        and (field == confirmed_field or (task == query and provenance.get(field) in {"rule", "model"}))
    }
    if confirmed_provider and qualification.get("current_provider") == confirmed_provider:
        facts["current_provider"] = confirmed_provider
    questions = [q["field"] for q in result["clarifying_questions"]["questions"] if q.get("field")]
    event = turn_event(
        query, facts=facts,
        questions=["current_provider" if field == "provider" else field for field in questions],
        missing=qualification["missing_required_fields"],
        awaiting=["current_provider" if field == "provider" else field for field in questions],
        issue="Human review requested" if result["status"] == "escalated" else None,
    )
    from .ownership_status import review_customer_status
    last_question = history[-1:] if history and history[-1]["role"] == "assistant" else []
    observed_status, observed_deferral = review_customer_status(
        query, last_question, interpretation, confirmed_customer_status,
    )
    if confirmed_field == 'customer_status':
        observed_status, observed_deferral = effective_status, False
    # Store new evidence only; deleting its source must remove the confirmation.
    if observed_status != "unknown" or observed_deferral:
        event["ownership_status"] = {
            "customer_status": observed_status,
            "status_deferred": observed_deferral,
            "source": "staff_confirmation" if observed_status == confirmed_customer_status else "customer_message",
            "confirmed_status_input": confirmed_customer_status,
        }
        if confirmed_field == 'customer_status':
            event['ownership_status']['source'] = 'customer_message'
            event['ownership_status']['reply_binding'] = 'pending_customer_status'
    if shared is not None:
        event["diagnostic_state"] = shared.model_dump(mode="json")
    result["reliability"] = active_query().snapshot()
    _save_trace(con, trace_id, case_id, query, result, round((perf_counter() - started) * 1000), event)
    result = {"case_id": case_id, "trace_id": trace_id, **result}
    cases.save_state(con, case_id, {
        **state,
        "last_trace_id": trace_id,
        "last_result": result,
        "interpretation": interpreted,
        "pending_provider_question": None,
        "pending_clarification": {
            "field": result["clarifying_questions"]["questions"][0]["field"], "task": task,
        } if result["status"] == "clarification_needed" else None,
    })
    return {**result, "conversation_state": load_conversation(con, case_id).to_dict()}


def _save_trace(con, trace_id, case_id, query, result, elapsed_ms, event):
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    event["timestamp"] = timestamp
    draft = result["response_draft"] or {}
    critic = result["critic"]
    questions = result["clarifying_questions"]["questions"]
    answer = draft.get("draft_text") or (questions[0]["text"] if questions else None)
    with con:
        if result.get("follow_up_selection"):
            con.execute(
                "INSERT INTO trace_steps (trace_id, case_id, step, component, output_json, ms, ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (trace_id, case_id, "follow_up_selection", "response_drafting",
                 json.dumps(result["follow_up_selection"]), None, timestamp),
            )
        con.execute(
            "INSERT INTO traces (id, ts, case_id, query, answer, reason, escalate, citations_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (trace_id, timestamp, case_id, query, answer, critic["reason"],
             int(result["status"] == "escalated"), json.dumps(draft.get("citations", []))),
        )
        con.executemany(
            "INSERT INTO trace_steps (trace_id, case_id, step, component, output_json, ms, ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(trace_id, case_id, step["action"], "langgraph", json.dumps(step), step.get("latency_ms"), timestamp)
             for step in result["steps"]],
        )
        con.executemany(
            "INSERT INTO trace_steps (trace_id, case_id, step, component, output_json, ms, ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(trace_id, case_id, call["tool_name"], "tool_registry", json.dumps(call),
              call["execution_duration_ms"], call["invocation_timestamp"])
             for call in result["tool_calls"]],
        )
        con.executemany(
            "INSERT INTO trace_steps (trace_id, case_id, step, component, output_json, ms, ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (trace_id, case_id, "conversation_state", "conversation_state", json.dumps(event), None, timestamp),
                (trace_id, case_id, "outcome", "workflow", json.dumps(critic), elapsed_ms, timestamp),
            ],
        )
