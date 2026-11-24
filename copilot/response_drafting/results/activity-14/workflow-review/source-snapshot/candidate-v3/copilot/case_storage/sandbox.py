# Source history: Deepshikha (f066c61), deepshikha/lbs-copilot. See copilot/enquiry_workflow/source-history.json.
"""Sandbox records store (mock CRM tickets / opportunities; Activity 15). The ONLY table this system can ever write to is sandbox_records.

propose()  builds a field-level diff against the current record and returns it; it never writes.
apply()    runs only after a human approved the pending action (case_storage/handlers.py) and re-checks the target and fields first.
"""
import json
import re
from datetime import datetime, timezone

SANDBOX_ID = re.compile(r"^(TKT|OPP)-\d{3,8}$")
ALLOWED_FIELDS = {"category", "api", "providers", "severity", "owner", "status", "stage", "next_step"}


class SandboxError(ValueError):
    pass


def _check(record_id: str, fields: dict) -> None:
    if not SANDBOX_ID.fullmatch(record_id or ""):
        raise SandboxError(f"'{record_id}' is not a sandbox record (expected TKT-nnnnn or OPP-nnnnn); nothing outside the sandbox can be changed")
    if not isinstance(fields, dict) or not fields:
        raise SandboxError("Supply at least one sandbox field.")
    if any(value is not None and type(value) not in {bool, int, float, str} for value in fields.values()):
        raise SandboxError("Sandbox fields must be scalar values.")
    bad = sorted(set(fields) - ALLOWED_FIELDS)
    if bad:
        raise SandboxError(f"fields not allowed in a sandbox update: {', '.join(bad)}")


def get(con, record_id: str) -> dict:
    row = con.execute("SELECT fields_json FROM sandbox_records WHERE record_id=?", (record_id,)).fetchone()
    return json.loads(row["fields_json"]) if row else {}


def diff(current: dict, fields: dict) -> dict:
    return {k: {"old": current.get(k), "new": v} for k, v in fields.items() if current.get(k) != v}


def propose(con, record_id: str, fields: dict) -> dict:
    """-> {record_id, mode: 'propose', fields, diff}. Pure read."""
    _check(record_id, fields)
    return {"record_id": record_id, "mode": "propose", "fields": dict(fields), "diff": diff(get(con, record_id), fields)}


def apply(con, payload: dict, action_id: int | None = None) -> dict:
    """Write an APPROVED proposal (possibly edited by the approver). Re-validates; returns the applied diff."""
    record_id, fields = payload["record_id"], payload.get("fields") or {}
    _check(record_id, fields)
    cur = get(con, record_id)
    changes = diff(cur, fields)
    new = {**cur, **fields}
    con.execute("INSERT OR REPLACE INTO sandbox_records (record_id, kind, fields_json, updated_at, last_action_id) VALUES (?,?,?,?,?)",
                (record_id, "ticket" if record_id.startswith("TKT") else "opportunity", json.dumps(new),
                 datetime.now(timezone.utc).isoformat(timespec="seconds"), action_id))
    con.commit()
    return {"applied_record": record_id, "applied_diff": changes}
