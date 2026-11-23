import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db.models import Tracker


SALES_FIELDS = ["company", "use_case", "device_count", "accuracy_requirement",
                "platform", "budget", "timeline", "decision_maker", "compliance", "status"]

SUPPORT_FIELDS = ["case_id", "affected_service", "error_codes", "device_id",
                  "steps_taken", "impact", "escalation_level", "status", "resolution"]


def get_or_create_tracker(db: Session, conversation_id: str, workflow: str) -> Tracker:
    tracker = db.query(Tracker).filter_by(conversation_id=conversation_id).first()
    if not tracker:
        tracker = Tracker(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            workflow=workflow,
            data={},
            pending_updates=[],
        )
        db.add(tracker)
        db.commit()
    return tracker


def propose_update(db: Session, conversation_id: str, workflow: str, updates: dict) -> dict:
    tracker = get_or_create_tracker(db, conversation_id, workflow)
    pending = list(tracker.pending_updates or [])
    pending.append({"updates": updates, "proposed_at": datetime.now(timezone.utc).isoformat()})
    tracker.pending_updates = pending
    db.commit()
    return {"status": "pending_approval", "proposed": updates}


def approve_update(db: Session, conversation_id: str) -> dict:
    tracker = db.query(Tracker).filter_by(conversation_id=conversation_id).first()
    if not tracker or not tracker.pending_updates:
        return {"status": "nothing_to_approve"}
    data = dict(tracker.data or {})
    for batch in tracker.pending_updates:
        data.update(batch["updates"])
    tracker.data = data
    tracker.pending_updates = []
    tracker.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "approved", "data": tracker.data}


def get_tracker_summary(db: Session, conversation_id: str) -> dict:
    tracker = db.query(Tracker).filter_by(conversation_id=conversation_id).first()
    if not tracker:
        return {}
    fields = SALES_FIELDS if tracker.workflow == "sales" else SUPPORT_FIELDS
    missing = [f for f in fields if not tracker.data.get(f)]
    return {"data": tracker.data, "missing_fields": missing, "pending_updates": tracker.pending_updates}
