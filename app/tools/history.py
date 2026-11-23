import uuid
from sqlalchemy.orm import Session
from app.db.models import Conversation, Message, AuditLog


def get_or_create_conversation(db: Session, conversation_id: str, workflow: str) -> Conversation:
    conv = db.query(Conversation).filter_by(id=conversation_id).first()
    if not conv:
        conv = Conversation(id=conversation_id, workflow=workflow)
        db.add(conv)
        db.commit()
    return conv


def add_message(db: Session, conversation_id: str, role: str, content: str, sources: list = None) -> Message:
    msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role=role,
        content=content,
        sources=sources or [],
    )
    db.add(msg)
    db.commit()
    return msg


def get_history(db: Session, conversation_id: str, limit: int = 20) -> list[dict]:
    msgs = (
        db.query(Message)
        .filter_by(conversation_id=conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{"role": m.role, "content": m.content, "sources": m.sources} for m in reversed(msgs)]


def log_audit(db: Session, conversation_id: str, step: str, action: str, details: dict):
    entry = AuditLog(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        step=step,
        action=action,
        details=details,
    )
    db.add(entry)
    db.commit()


def get_audit_trail(db: Session, conversation_id: str) -> list[dict]:
    logs = db.query(AuditLog).filter_by(conversation_id=conversation_id).order_by(AuditLog.created_at).all()
    return [{"step": l.step, "action": l.action, "details": l.details, "at": l.created_at.isoformat()} for l in logs]
