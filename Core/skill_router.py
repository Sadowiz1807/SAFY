from __future__ import annotations


def route_skill(intent: str) -> str:
    routes = {
        "create_database": "Create_database",
        "command_router": "Command_router",
        "database_context": "Database_context",
        "database_switch": "Database_switch",
        "schema_graph": "Schema_graph",
        "text_to_query": "Text_to_query",
        "query_guard": "Query_guard",
        "execute_box": "Execute_box",
        "execute_query": "Execute_query",
        "query_explain": "Query_explain",
        "query_repair": "Query_repair",
        "connected_read_only_query": "Text_to_query",
        "connected_destructive_query": "Text_to_query",
    }
    if intent in routes:
        return routes[intent]
    raise ValueError("SKILL_NOT_FOUND")
