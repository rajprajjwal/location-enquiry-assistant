"""Delete one saved enquiry and its workflow trace."""

import json

from .approval_sources import remove_approval_source


def delete_enquiry(con, trace_id: str) -> None:
    """Delete the selected turn atomically, keeping its case and approval decisions."""
    with con:
        con.execute("BEGIN IMMEDIATE")
        trace = con.execute(
            "SELECT * FROM traces WHERE id = ? AND case_id IS NOT NULL", (trace_id,)
        ).fetchone()
        if trace is None:
            raise ValueError("This enquiry is no longer available.")
        case_id = trace["case_id"]
        linked = con.execute(
            "SELECT id FROM messages WHERE case_id = ? AND turn_trace_id = ?", (case_id, trace_id)
        ).fetchall()
        message_ids = [row["id"] for row in linked] if linked else _legacy_messages(con, trace)
        remove_approval_source(con, trace)
        con.executemany(
            "DELETE FROM messages WHERE id = ? AND case_id = ?", [(i, case_id) for i in message_ids]
        )
        con.execute("DELETE FROM trace_steps WHERE trace_id = ?", (trace_id,))
        con.execute("DELETE FROM traces WHERE id = ?", (trace_id,))

        row = con.execute("SELECT state_json FROM cases WHERE id = ?", (case_id,)).fetchone()
        state = json.loads(row["state_json"] or "{}") if row else {}
        if state.get("last_trace_id") == trace_id:
            for key in ("last_trace_id", "last_result", "interpretation", "pending_provider_question", "pending_clarification"):
                state.pop(key, None)
            con.execute("UPDATE cases SET state_json = ? WHERE id = ?", (json.dumps(state), case_id))


def _legacy_messages(con, trace) -> list[int]:
    """Match older turns only when the saved query and message sequences agree."""
    case_id = trace["case_id"]
    turns = con.execute(
        "SELECT id, query FROM traces WHERE case_id = ? ORDER BY rowid", (case_id,)
    ).fetchall()
    messages = con.execute(
        "SELECT id, content FROM messages WHERE case_id = ? AND role = 'user' ORDER BY id", (case_id,)
    ).fetchall()
    if [turn["query"] for turn in turns] != [message["content"] for message in messages]:
        raise ValueError("This older trace could not be matched safely to its enquiry.")

    index = next(i for i, turn in enumerate(turns) if turn["id"] == trace["id"])
    first = messages[index]["id"]
    end = messages[index + 1]["id"] if index + 1 < len(messages) else None
    replies = con.execute(
        "SELECT id FROM messages WHERE case_id = ? AND id > ? AND (? IS NULL OR id < ?) "
        "AND turn_trace_id IS NULL AND role IN ('draft', 'clarification') AND content = ?",
        (case_id, first, end, end, trace["answer"]),
    ).fetchall()
    return [first, *(reply["id"] for reply in replies)]
