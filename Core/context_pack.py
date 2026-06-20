from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from Logging.redact import redact_obj
from Core.agent_state import AgentWorkflowState


@dataclass
class ContextPack:
    """Redacted context passed from SAFY runtime to skills/model calls."""

    session_id: str | None
    user_message: str
    target: str | None
    sandbox_id: str | None
    database_profile_id: str | None
    database_profile: dict[str, Any] | None = None
    schema_summary: str = ""
    state: AgentWorkflowState = field(default_factory=AgentWorkflowState)
    available_skills: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        profile = self.database_profile or {}
        safe_profile = redact_obj(
            {
                "profile_id": profile.get("profile_id"),
                "display_name": profile.get("display_name"),
                "provider": profile.get("provider"),
                "driver": profile.get("driver") or profile.get("dbms"),
                "database": profile.get("database"),
                "username": profile.get("username"),
                "base_url": profile.get("base_url"),
                "read_only": profile.get("read_only"),
                "real_db_readonly": profile.get("real_db_readonly"),
            }
        )
        return {
            "session_id": self.session_id,
            "target": self.target,
            "sandbox_id": self.sandbox_id,
            "database_profile_id": self.database_profile_id,
            "database_profile": safe_profile,
            "schema_summary": self.schema_summary,
            "state": self.state.to_dict(),
            "available_skills": list(self.available_skills or []),
        }

    def to_prompt_text(self, max_schema_chars: int = 6000) -> str:
        state = self.state
        schema = (self.schema_summary or "").strip()
        if len(schema) > max_schema_chars:
            schema = schema[:max_schema_chars] + "\n...[schema truncated]"
        pending = "none"
        if state.has_pending():
            pending = f"{state.pending_skill}.{state.pending_action}; missing={state.missing_slots()}; filled={state.filled_slots}"
        return (
            "SAFY context pack\n"
            f"- session_id: {self.session_id or 'none'}\n"
            f"- target: {self.target or 'auto'}\n"
            f"- database_profile_id: {self.database_profile_id or 'none'}\n"
            f"- sandbox_id: {self.sandbox_id or 'none'}\n"
            f"- pending_workflow: {pending}\n"
            f"- last_intent: {state.last_user_intent or 'none'}\n"
            f"- has_last_sql: {bool(state.last_sql)}\n"
            f"- last_check_id: {state.last_check_id or 'none'}\n"
            f"- available_skills: {', '.join(self.available_skills or [])}\n\n"
            f"Schema context:\n{schema or 'No schema context available.'}"
        )
