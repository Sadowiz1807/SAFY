from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class DatabaseSwitchSkill:
    def __init__(self, database_store=None, schema_graph_skill=None):
        self.database_store = database_store
        self.schema_graph_skill = schema_graph_skill

    def list_profiles(self) -> list[dict[str, Any]]:
        if not self.database_store:
            return []
        return self.database_store.read_all()

    def active_profile(self) -> dict[str, Any] | None:
        for profile in self.list_profiles():
            if profile.get("active"):
                return profile
        return None

    def load_active_schema_if_exists(self) -> dict[str, Any] | None:
        profile = self.active_profile()
        if not profile or not self.schema_graph_skill:
            return None
        return self.schema_graph_skill.load(profile.get("profile_id"), profile)
