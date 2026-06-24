from __future__ import annotations

from pathlib import Path

from Core.agent_state import AgentWorkflowState
from Core.workflow_engine import WorkflowEngine
from Core.semantic_action_plan import SemanticActionPlan, validate_plan_coherence, validate_sql_against_plan, DROP_DATABASE, READ
from Gateway.sql_classifier import classify_sql
from Gateway.statement_target_extractor import extract_targets
from Gateway.query_orchestrator import QueryOrchestrator, QueryOrchestratorContext
from Gateway.db_drivers.supabase_rest_driver import SupabaseRpcDriver
from Gateway.db_drivers.errors import DriverError


def test_context_transition_clears_opposing_target_and_invalidates_check_state():
    state = AgentWorkflowState()
    state.remember_check({"check_id": "check_old", "sql_hash": "hash_old"})
    state.remember_sql("SELECT * FROM old_table")

    state.transition_context(target="sandbox", sandbox_id="db_sqlserver", database_profile_id="db_sqlserver", driver="sqlserver", dialect="sqlserver")
    first_generation = state.context_generation
    assert state.current_target == "sandbox"
    assert state.current_sandbox_id == "db_sqlserver"
    assert state.current_database_profile_id is None
    assert state.last_check_id is None
    assert state.last_sql_hash is None
    assert state.last_sql is None

    state.remember_check({"check_id": "check_sandbox", "sql_hash": "hash_sandbox"})
    state.transition_context(target="connected_database", database_profile_id="db_supabase", driver="supabase_rpc", dialect="postgresql")
    assert state.context_generation == first_generation + 1
    assert state.current_target == "connected_database"
    assert state.current_database_profile_id == "db_supabase"
    assert state.current_sandbox_id is None
    assert state.last_check_id is None
    assert state.last_sql_hash is None


def test_workflow_engine_does_not_generate_natural_language_read_sql_before_semantic_planner():
    state = AgentWorkflowState()
    decision = WorkflowEngine().decide("in ra dữ liệu trong bảng a", state)
    assert not decision.handled
    assert decision.sql is None
    assert state.last_sql is None


def test_semantic_plan_rejects_incoherent_high_confidence_drop_database_unknown_object():
    plan = SemanticActionPlan(
        operation=DROP_DATABASE,
        scope="DATABASE",
        object_type="UNKNOWN",
        confidence=0.99,
        requires_confirmation=True,
    )
    result = validate_plan_coherence(plan)
    assert result["ok"] is False
    assert result["code"] == "SEMANTIC_PLAN_INCOHERENT"
    assert plan.can_generate_sql is False


def test_intent_sql_guard_rejects_target_mismatch():
    plan = SemanticActionPlan(operation=READ, scope="SINGLE_OBJECT", object_type="TABLE", targets=["orders"], confidence=1.0)
    result = validate_sql_against_plan("SELECT * FROM customers LIMIT 10", plan)
    assert result["ok"] is False
    assert result["code"] == "INTENT_SQL_TARGET_MISMATCH"


def test_target_extractor_returns_all_drop_table_targets():
    classification = classify_sql("DROP TABLE a, b, c;")
    targets = extract_targets(classification)
    assert targets.targets == ["a", "b", "c"]


def test_supabase_complex_read_has_stable_capability_error_code():
    driver = SupabaseRpcDriver()
    try:
        driver.execute_readonly("SELECT customers.id, orders.id FROM customers JOIN orders ON orders.customer_id = customers.id", {"base_url": "https://example.supabase.co", "api_key": "x"})
    except DriverError as exc:
        assert exc.error_code == "SUPABASE_READ_RPC_NOT_CONFIGURED"
    else:
        raise AssertionError("complex Supabase read should require read RPC/native PostgreSQL capability")


def test_query_execute_uses_stable_context_mismatch_error_codes(tmp_path):
    orchestrator = QueryOrchestrator(QueryOrchestratorContext(runtime_dir=tmp_path))
    check = orchestrator.check(
        "SELECT * FROM customers LIMIT 10",
        target="connected_database",
        database_profile_id="db_a",
        permission_mode="read_only",
        real_db_mode=True,
        database_profile={"driver": "fake"},
    )
    ok, error = orchestrator.execute(
        check_id=check["check_id"],
        sql_hash=check["sql_hash"],
        target="connected_database",
        user_decision="yes",
        confirmation_code=None,
        database_profile_id="db_b",
    )
    assert ok is False
    assert error["code"] == "QUERY_CHECK_PROFILE_MISMATCH"

    ok, error = orchestrator.execute(
        check_id=check["check_id"],
        sql_hash=check["sql_hash"],
        target="sandbox",
        user_decision="yes",
        confirmation_code=None,
        database_profile_id="db_a",
    )
    assert ok is False
    assert error["code"] == "QUERY_CHECK_TARGET_MISMATCH"


def test_dashboard_switch_database_resets_execute_context_and_chat_sends_active_profile_hint():
    source = Path("Apps/Web/dashboard.js").read_text(encoding="utf-8")
    assert "function resetExecuteContext" in source
    switch_body = source[source.index("async function switchActiveDatabase"):source.index("function databaseProfileIdFromDisplayName")]
    assert "resetExecuteContext" in switch_body
    send_body = source[source.index("async function sendChatMessage"):source.index("function renderSafetyReport")]
    assert "active_database_profile_id" in send_body
    assert "chatPayload.database_profile_id" in send_body
    assert "if (!command.isExecute && !readOnlyDbRequest && isDatabaseOperationRequest(rawText))" not in send_body
