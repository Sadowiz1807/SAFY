from __future__ import annotations

from Core.agent_state import AgentWorkflowState
from Gateway.db_drivers.supabase_rest_driver import SupabaseRpcDriver
from State.runtime_db import RuntimeDB


def test_agent_state_keeps_execution_summary_not_rows() -> None:
    state = AgentWorkflowState()
    state.remember_execute(
        {
            "success": True,
            "rows": [{"secret": "value"}],
            "columns": ["secret"],
            "metadata": {
                "row_count": 1,
                "rpc_response": {"rows": [{"secret": "value"}]},
            },
            "read_only": True,
        }
    )

    assert state.last_execution_result == {
        "success": True,
        "row_count": 1,
        "read_only": True,
    }
    assert "rows" not in state.to_dict()["last_execution_result"]


def test_runtime_db_omits_rows_and_provider_response(tmp_path) -> None:
    db = RuntimeDB(tmp_path / "runtime.sqlite3")
    db.create_session("chat_1")
    db.add_message(
        "chat_1",
        "assistant",
        "display result",
        metadata={
            "query_result": {"rows": [{"id": 1}], "row_count": 1},
            "metadata": {"rpc_response": {"success": True, "rows": [{"id": 1}]}},
        },
    )

    saved = db.list_messages("chat_1")[0]["metadata"]
    assert saved["query_result"]["rows"] == "<display-only rows omitted>"
    assert saved["metadata"]["rpc_response"] == "<provider response omitted>"


def test_supabase_rpc_success_does_not_return_raw_rpc_payload(monkeypatch) -> None:
    driver = SupabaseRpcDriver()
    monkeypatch.setattr(driver, "_request_json", lambda *args, **kwargs: ({"success": True, "status": "executed", "rows": [{"secret": "value"}]}, 200))

    result = driver.execute_user_sql(
        "CREATE TABLE demo (id integer)",
        {
            "provider": "supabase",
            "driver": "supabase_rpc",
            "dbms": "supabase_rpc",
            "connection_kind": "supabase_rpc",
            "base_url": "https://example.supabase.co/rest/v1",
            "api_key": "test-key",
        },
    )

    assert result["success"] is True
    assert result["metadata"]["rpc_status"] == "executed"
    assert "rpc_response" not in result["metadata"]


def test_sensitive_sql_literals_are_redacted_but_normal_sql_is_preserved() -> None:
    from Logging.redact import redact_text

    sensitive = "INSERT INTO users(username, password) VALUES ('alice', 'super-secret')"
    redacted = redact_text(sensitive)
    assert "alice" not in redacted
    assert "super-secret" not in redacted
    assert redacted.count("[REDACTED]") == 2

    normal = "SELECT * FROM users WHERE username='alice'"
    assert redact_text(normal) == normal


def test_json_runtime_db_applies_same_privacy_boundary(tmp_path) -> None:
    from State.json_runtime_db import JsonRuntimeDB

    db = JsonRuntimeDB(tmp_path / "sessions")
    db.add_message(
        "chat_1",
        "assistant",
        "INSERT INTO users(password) VALUES ('super-secret')",
        metadata={
            "generated_sql": "INSERT INTO users(password) VALUES ('super-secret')",
            "query_result": {"rows": [{"id": 1}]},
            "metadata": {"rpc_response": {"rows": [{"id": 1}]}},
        },
    )

    saved = db.list_messages("chat_1")[0]
    assert "super-secret" not in saved["content_redacted"]
    assert "super-secret" not in saved["metadata"]["generated_sql"]
    assert saved["metadata"]["query_result"]["rows"] == "<display-only rows omitted>"
    assert saved["metadata"]["metadata"]["rpc_response"] == "<provider response omitted>"
    assert db.check_version() == 2


def test_runtime_db_sanitizes_snapshot_and_lock_metadata(tmp_path: Path) -> None:
    from State.runtime_db import RuntimeDB

    db = RuntimeDB(tmp_path / "runtime.sqlite3")
    db.create_session("chat")
    db.register_workspace("ws", "chat", "<redacted>")
    snapshot = db.create_schema_snapshot(
        "ws",
        "test",
        "hash",
        {"tables": []},
        metadata={"rows": [{"password": "secret"}], "rpc_response": {"token": "abc"}},
    )
    lock = db.acquire_workspace_lock(
        "ws",
        "tester",
        "test",
        metadata={"rows": [{"api_key": "secret"}], "rpc_response": {"token": "abc"}},
    )

    assert snapshot["metadata"]["rows"] == "<display-only rows omitted>"
    assert snapshot["metadata"]["rpc_response"] == "<provider response omitted>"
    assert lock["metadata"]["rows"] == "<display-only rows omitted>"
    assert lock["metadata"]["rpc_response"] == "<provider response omitted>"


def test_json_runtime_session_filenames_do_not_collide(tmp_path: Path) -> None:
    from State.json_runtime_db import JsonRuntimeDB

    db = JsonRuntimeDB(tmp_path / "sessions")
    db.create_session("team/chat", metadata={"label": "slash"})
    db.create_session("team_chat", metadata={"label": "underscore"})

    assert db.get_session("team/chat")["metadata"]["label"] == "slash"
    assert db.get_session("team_chat")["metadata"]["label"] == "underscore"
    assert len(list((tmp_path / "sessions").glob("session_*.json"))) == 2
