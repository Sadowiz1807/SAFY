from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DatabaseContext:
    target: str
    sandbox_id: str | None
    database_profile_id: str | None
    database_profile: dict[str, Any] | None
    has_real_database: bool


class DatabaseContextSkill:
    def __init__(self, database_profile_loader=None, sandbox_manager=None):
        self.database_profile_loader = database_profile_loader
        self.sandbox_manager = sandbox_manager

    def get_profile(self, profile_id: str | None) -> dict[str, Any] | None:
        if not profile_id or not self.database_profile_loader:
            return None
        try:
            return self.database_profile_loader(profile_id)
        except Exception:
            return None

    def has_real_database(self, profile_id: str | None) -> bool:
        profile = self.get_profile(profile_id)
        if not profile:
            return False
        driver = str(profile.get("driver") or profile.get("dbms") or "").lower()
        return bool(profile.get("real_db_readonly")) and driver not in {"", "fake", "test"}

    def resolve(self, target: str | None, sandbox_id: str | None, database_profile_id: str | None) -> DatabaseContext:
        resolved_target = target
        profile = self.get_profile(database_profile_id)
        has_real = self.has_real_database(database_profile_id)

        if not resolved_target or resolved_target == "auto":
            resolved_target = "connected_database" if has_real else "sandbox"

        if resolved_target == "connected_database":
            return DatabaseContext("connected_database", None, database_profile_id, profile, has_real)

        resolved_sandbox_id = sandbox_id or "sandbox_default"
        if self.sandbox_manager and not sandbox_id:
            try:
                active = [s for s in self.sandbox_manager.list() if s.get("active") and s.get("state") != "deleted"]
                if active:
                    resolved_sandbox_id = active[0].get("sandbox_id") or active[0].get("id") or resolved_sandbox_id
            except Exception:
                pass
        return DatabaseContext("sandbox", resolved_sandbox_id, None, None, False)
