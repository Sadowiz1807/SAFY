from __future__ import annotations

from .skill_registry import SkillRegistry


_ROUTES = {
    "create_database": "create_database",
    "command_router": "command_router",
    "database_context": "database_context",
    "database_switch": "database_switch",
    "schema_graph": "schema_graph",
    # Compatibility alias for callers that still emit the old intent name.
    "text_to_query": "text_to_sql",
    "text_to_sql": "text_to_sql",
    "query_guard": "query_guard",
    "execute_box": "execute_box",
    "execute_query": "execute_query",
    "query_explain": "query_explain",
    "query_repair": "query_repair",
    "connected_read_only_query": "text_to_sql",
    "connected_destructive_query": "text_to_sql",
}


def route_skill(intent: str, registry: SkillRegistry | None = None) -> str:
    key = str(intent or "").strip().lower()
    name = _ROUTES.get(key)
    if not name:
        raise ValueError("SKILL_NOT_FOUND")
    if registry is not None:
        if not registry.has(name):
            raise ValueError("SKILL_NOT_REGISTERED")
        if name not in registry.active_names():
            raise ValueError("SKILL_DISABLED")
    return name
