"""Track which enquiries support an approval request."""

from datetime import datetime, timezone
import json


def backfill_approval_sources(con, case_id: str) -> None:
    """Link older approvals when the trace and approval-event sequences agree."""
    events = con.execute(
        "SELECT event.ts, event.detail_json FROM case_events AS event "
        "JOIN proposed_actions AS action ON action.id = json_extract(event.detail_json, '$.action_id') "
        "WHERE event.case_id = ? AND event.actor = 'orchestrator' AND action.type = 'escalation' "
        "AND event.event IN ('approval_requested', 'approval_payload_updated') ORDER BY event.id",
        (case_id,),
    ).fetchall()
    turns = con.execute(
        "SELECT id, ts FROM traces WHERE case_id = ? AND escalate = 1 "
        "AND (reason LIKE 'Escalation rule matched %' OR reason = 'Activity 2 identified a human handoff.') "
        "ORDER BY rowid",
        (case_id,),
    ).fetchall()
    deleted = con.execute(
        "SELECT DISTINCT trace_id FROM approval_enquiry_sources AS source "
        "JOIN proposed_actions AS action ON action.id = source.action_id "
        "WHERE action.case_id = ? AND source.deleted_at IS NOT NULL", (case_id,)
    ).fetchall()
    if deleted or len(events) != len(turns):
        return
    pairs = list(zip(events, turns))
    if any(
        not 0 <= (datetime.fromisoformat(turn["ts"]) - datetime.fromisoformat(event["ts"])).total_seconds() <= 5
        for event, turn in pairs
    ):
        return
    con.executemany(
        "INSERT OR IGNORE INTO approval_enquiry_sources (action_id, trace_id) "
        "SELECT id, ? FROM proposed_actions WHERE id = ? AND case_id = ? AND type = 'escalation'",
        [(turn["id"], json.loads(event["detail_json"])["action_id"], case_id) for event, turn in pairs],
    )


def remove_approval_source(con, trace) -> None:
    trace_id, case_id = trace["id"], trace["case_id"]
    backfill_approval_sources(con, case_id)
    links = con.execute(
        "SELECT source.action_id, action.status FROM approval_enquiry_sources AS source "
        "JOIN proposed_actions AS action ON action.id = source.action_id "
        "WHERE source.trace_id = ? AND action.case_id = ?", (trace_id, case_id)
    ).fetchall()
    if not links and trace["escalate"] and (trace["reason"] or "").startswith(
        ("Escalation rule matched ", "Activity 2 identified a human handoff.")
    ):
        raise ValueError("This older escalation could not be matched safely to its approval.")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cancelled = False
    for link in links:
        action_id = link["action_id"]
        con.execute(
            "UPDATE approval_enquiry_sources SET deleted_at = ?, payload_json = NULL "
            "WHERE action_id = ? AND trace_id = ?", (now, action_id, trace_id)
        )
        if link["status"] != "pending":
            continue
        remaining = con.execute(
            "SELECT payload_json FROM approval_enquiry_sources "
            "WHERE action_id = ? AND deleted_at IS NULL ORDER BY rowid DESC LIMIT 1", (action_id,)
        ).fetchone()
        if remaining is None:
            con.execute(
                "UPDATE proposed_actions SET status = 'cancelled', decided_at = ?, "
                "decision_note = 'Source enquiry deleted' WHERE id = ? AND status = 'pending'",
                (now, action_id),
            )
            cancelled = True
        elif remaining["payload_json"] is not None:
            con.execute(
                "UPDATE proposed_actions SET payload_json = ? WHERE id = ? AND status = 'pending'",
                (remaining["payload_json"], action_id),
            )
    if cancelled:
        con.execute(
            "UPDATE cases SET status = 'open', updated_at = ? "
            "WHERE id = ? AND status = 'awaiting_approval' "
            "AND NOT EXISTS (SELECT 1 FROM proposed_actions WHERE case_id = ? AND status = 'pending')",
            (now, case_id, case_id),
        )
