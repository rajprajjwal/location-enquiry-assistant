# Source history: Vinayagam Raja (ca2437d), master. See copilot/enquiry_workflow/source-history.json.
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ConversationState:
    """Structured state for one conversation, rebuilt from its stored turns."""

    conversation_id: str
    known_facts: Dict[str, Any] = field(default_factory=dict)
    missing_information: List[str] = field(default_factory=list)
    questions_asked: List[str] = field(default_factory=list)
    questions_answered: List[str] = field(default_factory=list)
    corrections: List[Dict[str, Any]] = field(default_factory=list)
    diagnostic_history: List[str] = field(default_factory=list)
    diagnostic_state: Dict[str, Any] = field(default_factory=dict)
    unresolved_issues: List[str] = field(default_factory=list)
    conversation_summary: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def add_known_fact(self, key: str, value: Any) -> None:
        self.known_facts[key] = value
        self.touch()

    def add_missing_information(self, field_name: str) -> None:
        if field_name not in self.missing_information:
            self.missing_information.append(field_name)
        self.touch()

    def remove_missing_information(self, field_name: str) -> None:
        self.missing_information = [item for item in self.missing_information if item != field_name]
        self.touch()

    def has_question_been_asked(self, question: str) -> bool:
        return question in self.questions_asked

    def ask_question(self, question: str) -> bool:
        if question in self.questions_asked:
            return False
        self.questions_asked.append(question)
        self.touch()
        return True

    def answer_question(self, question: str) -> None:
        if question not in self.questions_answered:
            self.questions_answered.append(question)
        self.touch()

    def apply_correction(self, field_name: str, new_value: Any, reason: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "field": field_name,
            "new_value": new_value,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.corrections.append(payload)
        self.known_facts[field_name] = new_value
        self.touch()
        return payload

    def add_diagnostic_step(self, step: str) -> None:
        self.diagnostic_history.append(step)
        self.touch()

    def add_unresolved_issue(self, issue: str) -> None:
        if issue not in self.unresolved_issues:
            self.unresolved_issues.append(issue)
        self.touch()

    def build_summary(self) -> str:
        facts = ", ".join(f"{key}={value}" for key, value in sorted(self.known_facts.items()))
        missing = ", ".join(self.missing_information) if self.missing_information else "none"
        open_issues = ", ".join(self.unresolved_issues) if self.unresolved_issues else "none"
        diagnostics = ", ".join(self.diagnostic_history[-3:]) or "none"
        self.conversation_summary = (
            f"Conversation {self.conversation_id}: known facts: {facts or 'none'}; "
            f"missing information: {missing}; unresolved issues: {open_issues}; "
            f"recent diagnostics: {diagnostics}."
        )[:1500]
        self.touch()
        return self.conversation_summary

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "known_facts": self.known_facts,
            "missing_information": list(self.missing_information),
            "questions_asked": list(self.questions_asked),
            "questions_answered": list(self.questions_answered),
            "corrections": list(self.corrections),
            "diagnostic_history": list(self.diagnostic_history),
            "diagnostic_state": self.diagnostic_state,
            "unresolved_issues": list(self.unresolved_issues),
            "conversation_summary": self.conversation_summary,
            "updated_at": self.updated_at,
        }
