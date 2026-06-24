from __future__ import annotations

import json
from pathlib import Path

import pytest

from Core.agent_state import AgentWorkflowState
from Core.semantic_action_plan import (
    DROP_TABLES,
    READ,
    SemanticActionPlan,
    validate_sql_against_plan,
)
from Core.skill_actions import TextToSqlSkill
from DataStore.profile_store import database_profile_store
from Gateway.db_drivers.errors import DriverError
from Gateway.db_drivers.supabase_rest_driver import SupabaseRpcDriver
from Gateway.query_orchestrator import QueryOrchestrator, QueryOrchestratorContext
from Sandbox.sandbox_manager import SandboxError, SandboxManager


class RecordingSupabaseDriver(SupabaseRpcDriver):
    def __init__(self):
        self.operations: list[tuple[str, str, dict | None]] = []

    def _secret(self, profile, secret_context=None):
        return "test-secret"

    def _request_json(self, profile, url, *, method="GET", accept="application/json", body=None, operation="request"):
        self.operations.append((operation, method, body))
        if operation == "execute_read_rpc_failed":
            raise AssertionError("unused")
        if operation == "execute_read_rpc":
            return [{"ok": True}], 200
        return [{"id": 1}], 200


def test_legacy_session_context_migration_sanitizes_contradictions_and_is_idempotent():
    raw = {
        "current_target": "sandbox",
        "current_database_profile_id": "db_supabase",
        "current_sandbox_id": "db_sqlserver",
        "last_sql": "SELECT * FROM stale",
        "last_sql_hash": "hash_stale",
        "last_check_id": "check_stale",
        "last_safety_result": {"check_id": "check_stale"},
        "pending_confirmation": {"code": "1234"},
        "context_generation": 2,
    }
    state = AgentWorkflowState.from_dict(raw)
    assert state.current_target == "sandbox"
    assert state.current_sandbox_id == "db_sqlserver"
    assert state.current_database_profile_id is None
    assert state.last_sql is None
    assert state.last_sql_hash is None
    assert state.last_check_id is None
    assert state.last_safety_result is None
    assert state.pending_confirmation is None
    assert state.context_generation == 3

    again = AgentWorkflowState.from_dict(state.to_dict())
    assert again.context_generation == 3
    assert again.to_dict()["current_database_profile_id"] is None


@pytest.mark.parametrize(
    "raw",
    [
        {"current_target": "connected_database", "current_database_profile_id": None, "current_sandbox_id": "s"},
        {"current_target": "sandbox", "current_database_profile_id": "db", "current_sandbox_id": None},
        {"current_target": "weird", "current_database_profile_id": "db", "current_sandbox_id": "s"},
    ],
)
def test_invalid_restored_context_fails_closed(raw):
    raw.update({"last_check_id": "check", "last_sql_hash": "hash", "last_sql": "SELECT 1", "context_generation": 9})
    state = AgentWorkflowState.from_dict(raw)
    assert state.current_target is None
    assert state.current_database_profile_id is None
    assert state.current_sandbox_id is None
    assert state.last_check_id is None
    assert state.last_sql_hash is None
    assert state.last_sql is None
    assert state.context_generation == 10


def test_backend_rejects_stale_context_schema_driver_and_dialect(tmp_path):
    orchestrator = QueryOrchestrator(QueryOrchestratorContext(runtime_dir=tmp_path))
    check = orchestrator.check(
        "SELECT * FROM customers LIMIT 10",
        target="connected_database",
        database_profile_id="db_a",
        permission_mode="read_only",
        real_db_mode=True,
        database_profile={"driver": "sqlite", "database": ":memory:"},
        context_generation=7,
        schema_generation="schema_a",
        driver="sqlite",
        dialect="sqlite",
    )
    for kwargs, code in [
        ({"context_generation": 8}, "QUERY_CHECK_CONTEXT_STALE"),
        ({"schema_generation": "schema_b"}, "QUERY_CHECK_SCHEMA_STALE"),
        ({"driver": "postgresql"}, "QUERY_CHECK_DRIVER_MISMATCH"),
        ({"dialect": "postgresql"}, "QUERY_CHECK_DIALECT_MISMATCH"),
    ]:
        ok, err = orchestrator.execute(
            check_id=check["check_id"],
            sql_hash=check["sql_hash"],
            target="connected_database",
            user_decision="yes",
            confirmation_code=None,
            database_profile_id="db_a",
            **kwargs,
        )
        assert ok is False
        assert err["code"] == code


def test_sqlserver_sandbox_capability_is_honest_offline(tmp_path):
    manager = SandboxManager(repo_root=tmp_path)
    created = manager.create({"id": "sqlserver_case", "engine": "sqlserver"})
    readiness = created["readiness"]
    assert readiness["validation_ready"]["status"] is False
    assert readiness["validation_ready"]["error_code"] == "SQLSERVER_WRITE_SANDBOX_UNSUPPORTED"
    with pytest.raises(SandboxError) as exc:
        manager.execute_validation("sqlserver_case", "CREATE TABLE a (id int)")
    assert exc.value.code == "SQLSERVER_WRITE_SANDBOX_UNSUPPORTED"


def test_sandbox_false_ready_metadata_does_not_validate_schema_dependent_dml(tmp_path):
    manager = SandboxManager(repo_root=tmp_path)
    created = manager.create({"id": "mysql_case", "engine": "mysql", "source_kind": "empty"})
    readiness = created["readiness"]
    assert readiness["overall_ready"]["status"] is False
    assert readiness["schema_ready"]["status"] is False
    with pytest.raises(SandboxError) as exc:
        manager.execute_validation("mysql_case", "INSERT INTO a VALUES (1)")
    assert exc.value.code == "SANDBOX_VALIDATION_NOT_READY"


def test_destructive_workflow_is_non_executable_and_has_no_check_material():
    plan = SemanticActionPlan(
        operation=DROP_TABLES,
        scope="ALL_TABLES",
        object_type="TABLE",
        data_effect="NONE",
        schema_effect="SCHEMA_DESTRUCTIVE",
        requires_schema=True,
        confidence=1.0,
    )
    result = TextToSqlSkill()._blocked_result(
        plan=plan,
        profile=None,
        target_payload={"target": "connected_database", "database_profile_id": "db_a"},
        schema_context_text="tables: a,b",
        skill_context_text="",
        explanation="blocked",
    )
    assert result["policy_blocked"] is True
    assert result["executable"] is False
    assert result["check_allowed"] is False
    assert result["execute_allowed"] is False
    assert result["check_id"] is None
    assert result["sql_hash"] is None


def test_forged_destructive_check_payload_is_blocked(tmp_path):
    orchestrator = QueryOrchestrator(QueryOrchestratorContext(runtime_dir=tmp_path))
    check = orchestrator.check(
        "DROP TABLE a;",
        target="connected_database",
        database_profile_id="db_a",
        permission_mode="credential_permissions",
        execution_path="execute_box_user",
        real_db_mode=True,
        database_profile={"driver": "sqlite", "database": ":memory:"},
    )
    assert check["check_passed"] is False
    assert check["error_code"] == "DESTRUCTIVE_SQL_BLOCKED"
    ok, err = orchestrator.execute(check["check_id"], check["sql_hash"], "connected_database", "yes", None, database_profile_id="db_a")
    assert ok is False
    assert err["code"] == "DESTRUCTIVE_SQL_BLOCKED"


def test_supabase_complex_read_routes_to_read_rpc_and_missing_rpc_is_stable():
    driver = RecordingSupabaseDriver()
    profile = {"base_url": "https://example.supabase.co", "api_key": "x", "read_rpc_function": "safy_read_sql", "read_rpc_argument": "sql_text"}
    result = driver.execute_readonly("SELECT customers.id FROM customers JOIN orders ON orders.customer_id = customers.id", profile)
    assert driver.operations[-1] == ("execute_read_rpc", "POST", {"sql_text": "SELECT customers.id FROM customers JOIN orders ON orders.customer_id = customers.id"})
    assert result["metadata"]["execution_transport"] == "postgrest_read_rpc"

    with pytest.raises(DriverError) as exc:
        SupabaseRpcDriver().execute_readonly("WITH x AS (SELECT 1) SELECT * FROM x", {"base_url": "https://example.supabase.co", "api_key": "x"})
    assert exc.value.error_code == "SUPABASE_READ_RPC_NOT_CONFIGURED"


def test_atomic_profile_activation_fault_injection_preserves_old_active(tmp_path, monkeypatch):
    store = database_profile_store(tmp_path / "profiles.json")
    base = {"display_name": "A", "dbms": "sqlite", "database": ":memory:", "user_query_access_mode": "read_only", "active": True}
    store.save({**base, "profile_id": "db_a"}, overwrite=True)
    store.save({**base, "profile_id": "db_b", "display_name": "B", "active": False}, overwrite=True)

    def fail_write(path, data):
        raise OSError("boom")

    monkeypatch.setattr("DataStore.profile_store.write_json_atomic", fail_write)
    with pytest.raises(OSError):
        store.activate("db_b")
    active = [p["profile_id"] for p in store.read_all() if p.get("active")]
    assert active == ["db_a"]


def test_get_active_profile_does_not_perform_hidden_live_io():
    source = Path("Apps/Api/safy_api/main.py").read_text(encoding="utf-8")
    body = source[source.index('def active_database_profile():'):source.index('@app.get("/profiles/model")')]
    assert "_test_database_profile_dict" not in body
    assert 'connection_status": "unknown"' in body


def test_sqlserver_system_database_grounding_helpers_and_schema_cache_key():
    from Gateway.db_drivers.sqlserver_driver import filter_application_schema_objects, is_system_database, schema_cache_identity

    assert is_system_database("sqlserver", "master") is True
    assert is_system_database("sqlserver", "user_db") is False
    objects = [{"schema": "sys", "name": "objects"}, {"schema": "dbo", "name": "orders"}]
    assert filter_application_schema_objects("sqlserver", "master", objects) == []
    assert filter_application_schema_objects("sqlserver", "user_db", objects) == [{"schema": "dbo", "name": "orders"}]
    assert schema_cache_identity({"profile_id": "db", "database": "master", "profile_generation": 1}) != schema_cache_identity({"profile_id": "db", "database": "app", "profile_generation": 1})


def test_auto_execute_contract_read_only_only(tmp_path):
    from Agent.agent_runtime import should_auto_execute

    assert should_auto_execute(auto_execute=True, plan=SemanticActionPlan(operation=READ, scope="SINGLE_OBJECT", object_type="TABLE", targets=["a"], confidence=1.0), target={"database_profile_id": "db", "context_generation": 1}, consistency={"ok": True}, capability={"supports_native_sql": True}) is True
    assert should_auto_execute(auto_execute=True, plan=SemanticActionPlan(operation=DROP_TABLES, scope="ALL_TABLES", object_type="TABLE", requires_schema=True, confidence=1.0), target={"database_profile_id": "db", "context_generation": 1}, consistency={"ok": True}, capability={"supports_native_sql": True}) is False


def test_target_scope_consistency_schema_mismatch_and_exact_scope():
    plan = SemanticActionPlan(operation=READ, scope="MULTIPLE_OBJECTS", object_type="TABLE", targets=["sales.a", "sales.b"], confidence=1.0)
    mismatch = validate_sql_against_plan("SELECT * FROM hr.a", plan)
    assert mismatch["code"] == "INTENT_SQL_TARGET_MISMATCH"
    missing = validate_sql_against_plan("SELECT * FROM sales.a", plan)
    assert missing["code"] == "INTENT_SQL_TARGET_SET_MISMATCH"
