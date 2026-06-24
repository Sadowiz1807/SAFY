from __future__ import annotations

import json
from pathlib import Path

from Audit.audit_store import AuditStore


def test_audit_store_drops_raw_sql_metadata_recursively(tmp_path: Path) -> None:
    sql = "CREATE TABLE private_example (secret TEXT)"
    store = AuditStore(tmp_path / "audit.sqlite3")

    event = store.write_event(
        event_type="test",
        action="test",
        sql_hash="hash_example",
        metadata={
            "sql": sql,
            "normalized_sql": sql,
            "nested": {"raw_sql": sql, "statement_type": "CREATE"},
            "decision": "ALLOW_AFTER_SANDBOX",
        },
    )

    serialized = json.dumps(event["metadata"], sort_keys=True)
    assert sql not in serialized
    assert "sql" not in event["metadata"]
    assert "normalized_sql" not in event["metadata"]
    assert "raw_sql" not in event["metadata"]["nested"]
    assert event["metadata"]["nested"]["statement_type"] == "CREATE"


def test_sandbox_audit_removes_nested_sql_and_result_rows(tmp_path: Path) -> None:
    from Sandbox.audit import SandboxAudit

    audit = SandboxAudit(tmp_path)
    event = audit.write(
        "sandbox_validation",
        "sandbox_demo",
        nested={
            "sql": "CREATE TABLE secret_data(id INTEGER)",
            "child": {"normalized_sql": "SELECT * FROM secret_data", "safe": True},
            "rows": [{"password": "secret"}],
        },
        safe_value="kept",
    )

    assert event["safe_value"] == "kept"
    assert event["nested"] == {"child": {"safe": True}}
    persisted = audit.read()
    assert persisted[0]["nested"] == {"child": {"safe": True}}
