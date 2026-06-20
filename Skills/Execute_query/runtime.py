from __future__ import annotations

from typing import Any


class ExecuteQuerySkill:
    def __init__(self, query_orchestrator):
        self.query_orchestrator = query_orchestrator

    def execute_checked(self, check_id: str, sql_hash: str, target: dict[str, Any], user_decision: str | None = None, confirmation_code: str | None = None, row_limit: int = 100) -> tuple[bool, dict[str, Any]]:
        return self.query_orchestrator.execute(
            check_id=check_id,
            sql_hash=sql_hash,
            target=target.get("target") or "connected_database",
            user_decision=user_decision,
            confirmation_code=confirmation_code,
            database_profile_id=target.get("database_profile_id"),
            row_limit=row_limit,
            sandbox_id=target.get("sandbox_id"),
        )
