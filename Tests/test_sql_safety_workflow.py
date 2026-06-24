from __future__ import annotations

from pathlib import Path

from Gateway.query_orchestrator import QueryOrchestrator, QueryOrchestratorContext
from Gateway.sql_classifier import BATCH, CREATE, MULTI_STATEMENT, TRANSACTION_CONTROL, UNKNOWN, classify_sql


class RecordingSandbox:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def execute_validation(self, sandbox_id: str, sql: str) -> dict:
        self.calls.append((sandbox_id, sql))
        return {
            "success": True,
            "status": "sandbox_passed",
            "sandbox_id": sandbox_id,
            "metadata": {"rolled_back": True},
        }


def make_orchestrator(tmp_path: Path) -> tuple[QueryOrchestrator, RecordingSandbox]:
    orchestrator = QueryOrchestrator(QueryOrchestratorContext(tmp_path))
    sandbox = RecordingSandbox()
    orchestrator.sandbox_manager = sandbox  # type: ignore[assignment]
    return orchestrator, sandbox


def test_single_markdown_fence_is_unwrapped_before_classification() -> None:
    classified = classify_sql("```sql\nCREATE TABLE demo (id INTEGER);\n```")
    assert classified.statement_type == CREATE
    assert classified.normalized.normalized_sql == "CREATE TABLE demo (id INTEGER)"
    assert classified.is_multi_statement is False


def test_prose_around_fence_remains_fail_closed() -> None:
    classified = classify_sql("Here is the SQL:\n```sql\nCREATE TABLE demo (id INTEGER);\n```")
    assert classified.statement_type in {UNKNOWN, MULTI_STATEMENT}


def test_fenced_create_reaches_sandbox_validation(tmp_path: Path) -> None:
    orchestrator, sandbox = make_orchestrator(tmp_path)
    result = orchestrator.check(
        sql="```sql\nCREATE TABLE demo (id INTEGER);\n```",
        target="connected_database",
        database_profile_id="db_demo",
        permission_mode="credential_permissions",
        execution_path="execute_box_user",
        real_db_mode=True,
        database_profile={"profile_id": "db_demo"},
        sandbox_id="db_db_demo",
    )

    assert result["statement_type"] == CREATE
    assert result["allowed_to_attempt"] is True
    assert result["sandbox_validated"] is True
    assert result["decision"] == "ALLOW_AFTER_SANDBOX"
    assert sandbox.calls == [("db_db_demo", "CREATE TABLE demo (id INTEGER)")]


def test_user_schema_batch_reaches_sandbox_and_reports_real_targets(tmp_path: Path) -> None:
    orchestrator, sandbox = make_orchestrator(tmp_path)
    sql = """
    CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS shipments (id INTEGER PRIMARY KEY, order_id INTEGER REFERENCES orders(id));
    CREATE INDEX IF NOT EXISTS idx_shipments_order_id ON shipments(order_id);
    """
    result = orchestrator.check(
        sql=sql,
        target="connected_database",
        database_profile_id="db_supabase",
        permission_mode="credential_permissions",
        execution_path="execute_box_user",
        real_db_mode=True,
        database_profile={"profile_id": "db_supabase", "driver": "supabase_rpc"},
        sandbox_id="db_db_supabase",
    )

    assert result["statement_type"] == BATCH
    assert result["statement_count"] == 3
    assert result["statement_types"] == [CREATE, CREATE, CREATE]
    assert result["targets"] == ["orders", "shipments"]
    assert "IF" not in result["targets"]
    assert result["check_passed"] is True
    assert result["allowed_to_attempt"] is True
    assert result["safety_status"] == "sandbox_passed"
    assert result["decision"] == "ALLOW_AFTER_SANDBOX"
    assert len(sandbox.calls) == 1
    assert "CREATE INDEX IF NOT EXISTS" in sandbox.calls[0][1]


def test_unsafe_statement_inside_user_batch_blocks_before_sandbox(tmp_path: Path) -> None:
    orchestrator, sandbox = make_orchestrator(tmp_path)
    result = orchestrator.check(
        sql="CREATE TABLE demo (id INTEGER); DROP TABLE demo;",
        target="connected_database",
        database_profile_id="db_demo",
        permission_mode="credential_permissions",
        execution_path="execute_box_user",
        real_db_mode=True,
        database_profile={"profile_id": "db_demo"},
        sandbox_id="db_db_demo",
    )

    assert result["statement_type"] == BATCH
    assert result["check_passed"] is False
    assert result["allowed_to_attempt"] is False
    assert result["error_code"] == "DESTRUCTIVE_SQL_BLOCKED"
    assert result["blocked_statement_indexes"] == [2]
    assert sandbox.calls == []


def test_supabase_batch_wrapper_is_one_atomic_do_command() -> None:
    from Gateway.db_drivers.supabase_rest_driver import _atomic_postgres_batch

    wrapped = _atomic_postgres_batch([
        "CREATE TABLE orders (id INTEGER PRIMARY KEY)",
        "CREATE INDEX idx_orders_id ON orders(id)",
    ])
    assert wrapped.startswith("DO $safy_batch$")
    assert wrapped.count("EXECUTE $safy_stmt_") == 2
    assert "CREATE TABLE orders" in wrapped
    assert "CREATE INDEX idx_orders_id" in wrapped


def test_transaction_control_is_blocked_before_sandbox(tmp_path: Path) -> None:
    orchestrator, sandbox = make_orchestrator(tmp_path)
    result = orchestrator.check(
        sql="BEGIN;",
        target="connected_database",
        database_profile_id="db_demo",
        permission_mode="credential_permissions",
        execution_path="execute_box_user",
        real_db_mode=True,
        database_profile={"profile_id": "db_demo"},
        sandbox_id="db_db_demo",
    )

    assert result["statement_type"] == TRANSACTION_CONTROL
    assert result["allowed_to_attempt"] is False
    assert result["error_code"] == "TRANSACTION_CONTROL_BLOCKED"
    assert sandbox.calls == []


def test_user_cancel_consumes_and_removes_check(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path)
    checked = orchestrator.check(
        sql="CREATE TABLE demo (id INTEGER);",
        target="connected_database",
        database_profile_id="db_demo",
        permission_mode="credential_permissions",
        execution_path="execute_box_user",
        real_db_mode=True,
        database_profile={"profile_id": "db_demo"},
        sandbox_id="db_db_demo",
    )

    ok, payload = orchestrator.execute(
        check_id=checked["check_id"],
        sql_hash=checked["sql_hash"],
        target="connected_database",
        user_decision="no",
        confirmation_code=None,
        database_profile_id="db_demo",
        sandbox_id="db_db_demo",
    )

    assert ok is True
    assert payload["status"] == "cancelled"
    assert checked["check_id"] not in orchestrator.checks


def test_row_mutations_do_not_invalidate_schema_snapshot() -> None:
    from Gateway.risk_analyzer import analyze_risk
    from Gateway.statement_target_extractor import extract_targets

    for sql in (
        "INSERT INTO demo (id) VALUES (1)",
        "UPDATE demo SET id = 2 WHERE id = 1",
        "DELETE FROM demo WHERE id = 1",
    ):
        classification = classify_sql(sql)
        risk = analyze_risk(classification, extract_targets(classification))
        assert risk.invalidates_schema_snapshot is False


def test_read_only_profile_blocks_mutation_before_sandbox(tmp_path: Path) -> None:
    orchestrator, sandbox = make_orchestrator(tmp_path)
    result = orchestrator.check(
        sql="CREATE TABLE demo (id INTEGER);",
        target="connected_database",
        database_profile_id="db_demo",
        permission_mode="read_only",
        execution_path="execute_box_user",
        real_db_mode=True,
        database_profile={"profile_id": "db_demo", "user_query_access_mode": "read_only"},
        sandbox_id="db_db_demo",
    )

    assert result["allowed_to_attempt"] is False
    assert result["error_code"] == "DATABASE_READ_ONLY"
    assert sandbox.calls == []


def test_disabled_profile_blocks_select_before_execution(tmp_path: Path) -> None:
    orchestrator, sandbox = make_orchestrator(tmp_path)
    result = orchestrator.check(
        sql="SELECT 1;",
        target="connected_database",
        database_profile_id="db_demo",
        permission_mode="disabled",
        execution_path="execute_box_user",
        real_db_mode=True,
        database_profile={"profile_id": "db_demo", "user_query_access_mode": "disabled"},
        sandbox_id="db_db_demo",
    )

    assert result["allowed_to_attempt"] is False
    assert result["error_code"] == "DATABASE_ACCESS_DISABLED"
    assert sandbox.calls == []


def test_same_check_cannot_execute_twice_under_concurrency(tmp_path: Path, monkeypatch) -> None:
    from concurrent.futures import ThreadPoolExecutor
    import time
    import Gateway.query_orchestrator as orchestrator_module

    orchestrator, _ = make_orchestrator(tmp_path)
    checked = orchestrator.check(
        sql="CREATE TABLE demo (id INTEGER);",
        target="connected_database",
        database_profile_id="db_demo",
        permission_mode="credential_permissions",
        execution_path="execute_box_user",
        real_db_mode=True,
        database_profile={
            "profile_id": "db_demo",
            "provider": "self_hosted",
            "driver": "sqlite",
            "dbms": "sqlite",
            "database": str(tmp_path / "unused.sqlite"),
        },
        sandbox_id="db_db_demo",
    )

    calls = 0

    def fake_execute(*args, **kwargs):
        nonlocal calls
        calls += 1
        time.sleep(0.05)
        return {
            "success": True,
            "driver": "test",
            "row_count": 0,
            "metadata": {"row_count": 0, "execution_transport": "test"},
        }

    monkeypatch.setattr(orchestrator_module, "driver_execute_user_sql", fake_execute)

    def run_once():
        return orchestrator.execute(
            check_id=checked["check_id"],
            sql_hash=checked["sql_hash"],
            target="connected_database",
            user_decision="yes",
            confirmation_code=None,
            database_profile_id="db_demo",
            sandbox_id="db_db_demo",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run_once(), range(2)))

    assert calls == 1
    assert sum(1 for ok, _ in results if ok) == 1
    assert sum(1 for ok, _ in results if not ok) == 1


def test_execute_request_rejects_out_of_range_row_limits() -> None:
    import pytest
    from pydantic import ValidationError

    from Apps.Api.safy_api.schemas import QueryExecuteRequest

    assert QueryExecuteRequest(row_limit=1).row_limit == 1
    assert QueryExecuteRequest(row_limit=1000).row_limit == 1000
    with pytest.raises(ValidationError):
        QueryExecuteRequest(row_limit=0)
    with pytest.raises(ValidationError):
        QueryExecuteRequest(row_limit=1001)


def test_security_sensitive_ddl_is_blocked_before_sandbox(tmp_path: Path) -> None:
    orchestrator, sandbox = make_orchestrator(tmp_path)
    for sql in (
        "CREATE USER unsafe_user WITH PASSWORD 'secret';",
        "CREATE FUNCTION unsafe_fn() RETURNS void AS 'x' LANGUAGE c;",
        "ALTER TABLE accounts DISABLE ROW LEVEL SECURITY;",
        "CREATE POLICY open_access ON accounts USING (true);",
    ):
        result = orchestrator.check(
            sql=sql,
            target="connected_database",
            database_profile_id="db_demo",
            permission_mode="credential_permissions",
            execution_path="execute_box_user",
            real_db_mode=True,
            database_profile={"profile_id": "db_demo"},
            sandbox_id="db_db_demo",
        )
        assert result["statement_type"] == "ADMIN_SECURITY"
        assert result["allowed_to_attempt"] is False
        assert result["error_code"] == "SQL_POLICY_BLOCKED"
    assert sandbox.calls == []


def test_failed_mutation_attempt_consumes_one_time_check(tmp_path: Path, monkeypatch) -> None:
    from Gateway.db_drivers.errors import DriverError
    import Gateway.query_orchestrator as orchestrator_module

    orchestrator, _ = make_orchestrator(tmp_path)
    checked = orchestrator.check(
        sql="CREATE TABLE demo (id INTEGER);",
        target="connected_database",
        database_profile_id="db_demo",
        permission_mode="credential_permissions",
        execution_path="execute_box_user",
        real_db_mode=True,
        database_profile={"profile_id": "db_demo", "driver": "sqlite"},
        sandbox_id="db_db_demo",
    )

    def fail_after_possible_commit(*args, **kwargs):
        raise DriverError("DB_CONNECTION_FAILED", "ambiguous commit state")

    monkeypatch.setattr(orchestrator_module, "driver_execute_user_sql", fail_after_possible_commit)
    ok, result = orchestrator.execute(
        check_id=checked["check_id"],
        sql_hash=checked["sql_hash"],
        target="connected_database",
        user_decision="yes",
        confirmation_code=None,
        database_profile_id="db_demo",
        sandbox_id="db_db_demo",
    )
    assert ok is False
    assert result["code"] == "DB_CONNECTION_FAILED"
    assert checked["check_id"] not in orchestrator.checks

    ok_again, result_again = orchestrator.execute(
        check_id=checked["check_id"],
        sql_hash=checked["sql_hash"],
        target="connected_database",
        user_decision="yes",
        confirmation_code=None,
        database_profile_id="db_demo",
        sandbox_id="db_db_demo",
    )
    assert ok_again is False
    assert result_again["code"] == "QUERY_CHECK_REQUIRED"
