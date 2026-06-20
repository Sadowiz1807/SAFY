from __future__ import annotations


def plan_intent(intent: str, target: str) -> dict:
    if intent == "create_database":
        if target != "sandbox":
            return {"status": "blocked", "error_code": "SKILL_POLICY_BLOCKED", "steps": []}
        return {"status": "ready", "steps": ["load_skill", "compile_policy", "provider_plan", "validate_sql", "sandbox_execute", "schema_readback"]}
    if intent == "connected_read_only_query":
        if target != "connected_database":
            return {"status": "blocked", "error_code": "TARGET_NOT_SUPPORTED", "steps": []}
        return {"status": "connected_read_only", "steps": ["classify_request", "agent_read_only_preview", "audit_response"]}
    if intent == "connected_destructive_query":
        return {"status": "blocked", "error_code": "AGENT_CONNECTED_DB_DESTRUCTIVE_SQL_BLOCKED", "steps": []}
    return {"status": "blocked", "error_code": "INTENT_UNCLEAR", "steps": []}
