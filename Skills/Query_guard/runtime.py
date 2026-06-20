from __future__ import annotations

from typing import Any


class QueryGuardSkill:
    def __init__(self, query_orchestrator):
        self.query_orchestrator = query_orchestrator

    def check(self, sql: str, target: dict[str, Any], database_profile: dict[str, Any] | None = None, permission_mode: str = "read_only", execution_path: str = "skill_query_guard") -> dict[str, Any]:
        return self.query_orchestrator.check(
            sql=sql,
            target=target.get("target") or "connected_database",
            database_profile_id=target.get("database_profile_id"),
            permission_mode=permission_mode,
            execution_path=execution_path,
            sandbox_id=target.get("sandbox_id"),
            real_db_mode=bool(target.get("target") == "connected_database" and database_profile),
            database_profile=database_profile,
        )
