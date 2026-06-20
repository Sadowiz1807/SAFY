from __future__ import annotations

from typing import Any


class ExecuteBoxSkill:
    def set_draft(self, sql: str, explanation: str, target: dict[str, Any], provider_profile_id: str | None = None) -> dict[str, Any]:
        return {
            "draft_ready": bool(sql),
            "sql": sql,
            "summary": explanation or "SQL draft generated. Review it before running Check Safety.",
            "next_steps": ["review_sql", "check_safety", "execute_if_allowed"],
            "target": target.get("target"),
            "database_profile_id": target.get("database_profile_id"),
            "provider_profile_id": provider_profile_id,
            "auto_executed": False,
        }
