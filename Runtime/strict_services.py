from __future__ import annotations

from pathlib import Path
from typing import Any

from DataStore.config_loader import get_repo_root
from DataStore.profile_store import ProfileStoreError, database_profile_store
from DataStore.sandbox_rule_store import SandboxRuleStore
from Core.sandbox_rule_engine import SandboxRuleEngine
from Core.rules.semantic_compiler import compile_rule
from Gateway.query_orchestrator import QueryOrchestrator, QueryOrchestratorContext
from Runtime.live_runtime import RULE_MANAGER, EVENT_BUS, CONTEXT_BUILDER, mark

REPO_ROOT = get_repo_root()
RULE_STORE = SandboxRuleStore((REPO_ROOT / "Data" / "sandbox_rules").resolve())
RULE_ENGINE = SandboxRuleEngine()
QUERY_ORCHESTRATOR = QueryOrchestrator(QueryOrchestratorContext((REPO_ROOT / "Data" / "sessions").resolve(), test_runtime_mode=False))


def _database_profile_for_check(database_profile_id: str | None) -> dict[str, Any] | None:
    if not database_profile_id:
        return None
    try:
        return database_profile_store(REPO_ROOT / "Data" / "safy_profiles.json").get(database_profile_id)
    except ProfileStoreError as exc:
        if exc.code == "PROFILE_NOT_FOUND":
            return None
        raise


def _schema_for_rule_profile(database_profile_id: str | None) -> dict[str, Any]:
    return {"database_profile_id": database_profile_id, "tables": []}


def validation_message(report: dict[str, Any]) -> str:
    status = report.get("status")
    if status in {"draft", "active"}:
        return "Sandbox rule saved and activated."
    if status == "conflict_rule":
        return "Sandbox rule was not saved because it conflicts with an active rule."
    if status == "warning_only":
        warnings = report.get("warnings") or []
        return "Sandbox rule was not saved: " + (warnings[0] if warnings else "The rule is ambiguous and cannot be enforced deterministically.")
    return "Sandbox rule was not saved because validation did not pass."


def save_rule(payload: dict[str, Any]) -> dict[str, Any]:
    mark("routes.rules.save")
    db = payload.get("database_profile_id") or "db_default"
    sb = payload.get("sandbox_id") or "sandbox_default"
    rid = payload.get("rule_id")
    existing = RULE_STORE.get_rule(db, sb, rid) if rid else None
    candidate = {
        **(existing or {}),
        "rule_id": rid or "rule_pending_save",
        "database_profile_id": db,
        "sandbox_id": sb,
        "connection_name": payload.get("connection_name"),
        "source_type": payload.get("source_type") or "manual_text",
        "source_filename": payload.get("source_filename"),
        "raw_text": payload.get("raw_text") or "",
        "severity": payload.get("severity") or "block",
    }
    active = [r for r in RULE_STORE.list_rules(db, sb).get("active_rules", []) if r.get("rule_id") != rid]
    report = RULE_ENGINE.validate_rule(candidate, active, _schema_for_rule_profile(db))
    if report.get("status") != "draft":
        return {"saved": False, "rule": None, "validation_report": report, "message": validation_message(report), "served_by": "routes/rules.py"}
    if existing:
        rule = {**existing, **candidate, "rule_id": existing.get("rule_id")}
    else:
        rule = RULE_STORE.create_draft(database_profile_id=db, sandbox_id=sb, raw_text=candidate["raw_text"], connection_name=candidate.get("connection_name"), source_type=candidate.get("source_type") or "manual_text", source_filename=candidate.get("source_filename"), severity=candidate.get("severity") or "block")
    updated, activate_report = RULE_ENGINE.activate(rule, active, _schema_for_rule_profile(db))
    updated["dsl"] = compile_rule(updated.get("raw_text", ""))
    RULE_STORE.save_rule(updated)
    path = RULE_STORE.write_validation_report(updated, activate_report)
    RULE_MANAGER.save_rule(updated, db, sb)
    EVENT_BUS.emit("rules.saved", {"rule": updated, "validation_report": activate_report})
    return {"saved": True, "rule": updated, "validation_report": activate_report, "validation_report_path": str(path), "message": "Sandbox rule saved and activated.", "served_by": "routes/rules.py", "ui_patch": {"op": "merge", "target": "rules", "value": RULE_STORE.list_rules(db, sb).get("active_rules", [])}}


def list_rules(database_profile_id: str | None, sandbox_id: str = "sandbox_default") -> dict[str, Any]:
    mark("routes.rules.list")
    data = RULE_STORE.list_rules(database_profile_id or "db_default", sandbox_id)
    data["served_by"] = "routes/rules.py"
    return data


def disable_rule(payload: dict[str, Any]) -> dict[str, Any] | None:
    mark("routes.rules.disable")
    db = payload.get("database_profile_id") or "db_default"
    sb = payload.get("sandbox_id") or "sandbox_default"
    disabled = RULE_STORE.disable(db, sb, payload.get("rule_id"))
    if disabled:
        RULE_MANAGER.disable_rule(payload.get("rule_id"), db, sb)
        EVENT_BUS.emit("rules.disabled", {"rule": disabled})
    return disabled


def check_query(payload: dict[str, Any]) -> dict[str, Any]:
    mark("routes.query.query_check")
    session_id = payload.get("session_id") or payload.get("chat_id") or "default"
    CONTEXT_BUILDER.build(session_id, payload.get("sql") or "")
    db = payload.get("database_profile_id")
    sb = payload.get("sandbox_id") or (f"db_{db}" if db else None)
    database_profile = _database_profile_for_check(db)
    permission_mode = payload.get("user_query_access_mode") or (database_profile or {}).get("user_query_access_mode") or "credential_permissions"
    driver = payload.get("driver") or (database_profile or {}).get("driver") or (database_profile or {}).get("dbms")
    dialect = payload.get("dialect") or (database_profile or {}).get("dialect")
    check = QUERY_ORCHESTRATOR.check(
        sql=payload.get("sql") or "",
        target=payload.get("target") or "sandbox",
        database_profile_id=db,
        permission_mode=permission_mode,
        execution_path="execute_box_user",
        expose_confirmation_code=False,
        real_db_mode=bool(payload.get("real_db_mode")),
        database_profile=database_profile,
        sandbox_id=sb,
        context_generation=payload.get("context_generation"),
        schema_generation=payload.get("schema_generation"),
        driver=driver,
        dialect=dialect,
    )
    # Route-owned rule enforcement must always run, not only when the old
    # sandbox manager is unavailable. Otherwise Check Safety may return a
    # generic policy block and hide the actual active-rule violation.
    from Core.sql.guard import check_sql
    active_rules = RULE_STORE.list_rules(db or "db_default", sb or "sandbox_default").get("active_rules", [])
    dsl_rules = []
    for r in active_rules:
        dsl = r.get("dsl") or compile_rule(r.get("raw_text", ""))
        dsl_rules.append(dsl)
    strict = check_sql(payload.get("sql") or "", dsl_rules)
    strict_reasons = strict.get("data", {}).get("reasons", []) if strict.get("success") else []
    if strict.get("data", {}).get("allowed") is False:
        check["allowed_to_attempt"] = False
        check["error_code"] = "SANDBOX_RULE_BLOCKED"
        existing = list(check.get("blockers") or [])
        for reason in strict_reasons:
            if reason not in existing:
                existing.append(reason)
        check["blockers"] = existing
        warnings = list(check.get("warnings") or [])
        for reason in strict_reasons:
            if reason not in warnings:
                warnings.append(reason)
        check["warnings"] = warnings
    check["rule_check"] = strict.get("data", strict)
    check["runtime_snapshot_built"] = True
    check["served_by"] = "routes/query.py"
    EVENT_BUS.emit("check_safety.completed", {"result": check})
    return check


def execute_query(payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    mark("routes.query.query_execute")
    ok, result = QUERY_ORCHESTRATOR.execute(
        check_id=payload.get("check_id"),
        sql_hash=payload.get("sql_hash"),
        target=payload.get("target") or "sandbox",
        user_decision=payload.get("user_decision"),
        confirmation_code=payload.get("confirmation_code"),
        database_profile_id=payload.get("database_profile_id"),
        row_limit=int(payload.get("row_limit") or 100),
        sandbox_id=payload.get("sandbox_id"),
        context_generation=payload.get("context_generation"),
        schema_generation=payload.get("schema_generation"),
        driver=payload.get("driver"),
        dialect=payload.get("dialect"),
    )
    EVENT_BUS.emit("query.execute.completed", {"success": ok, "result": result})
    return ok, result
