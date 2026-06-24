from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import sqlite3
import uuid

from .audit_schema import AUDIT_SCHEMA, AUDIT_SCHEMA_VERSION
from Logging.redact import redact_obj, redact_text

_SQL_METADATA_KEYS = {
    "sql",
    "raw_sql",
    "normalized_sql",
    "redacted_sql",
    "executed_sql",
    "query_text",
}


def _drop_sql_metadata(value: Any) -> Any:
    """Remove SQL text from persisted audit metadata at the storage boundary."""
    if isinstance(value, dict):
        return {
            key: _drop_sql_metadata(item)
            for key, item in value.items()
            if str(key).lower() not in _SQL_METADATA_KEYS
        }
    if isinstance(value, list):
        return [_drop_sql_metadata(item) for item in value]
    if isinstance(value, tuple):
        return [_drop_sql_metadata(item) for item in value]
    return value


class AuditStoreError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AuditStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(AUDIT_SCHEMA)
            current = conn.execute("SELECT version FROM schema_version WHERE component='audit'").fetchone()
            if current and current[0] > AUDIT_SCHEMA_VERSION:
                raise AuditStoreError("RUNTIME_SCHEMA_VERSION_MISMATCH", "Audit DB schema version is newer than this code.")
            conn.execute("INSERT OR REPLACE INTO schema_version(component, version, applied_at, notes) VALUES (?, ?, ?, ?)", ("audit", AUDIT_SCHEMA_VERSION, now_iso(), "Stage 2 audit foundation"))

    def write_event(self, **event: Any) -> dict[str, Any]:
        self.init()
        timestamp = now_iso()
        metadata = redact_obj(_drop_sql_metadata(event.get("metadata") or {}))
        record = {
            "audit_id": event.get("audit_id") or f"audit_{uuid.uuid4().hex}",
            "event_type": event.get("event_type") or "generic",
            "actor_type": event.get("actor_type"),
            "actor_id": event.get("actor_id"),
            "action": event.get("action") or "unknown",
            "target_type": event.get("target_type"),
            "target_id": event.get("target_id"),
            "risk_level": event.get("risk_level"),
            "status": event.get("status") or "created",
            "created_at": event.get("created_at") or timestamp,
            "updated_at": event.get("updated_at") or timestamp,
            "request_id": event.get("request_id"),
            "check_id": event.get("check_id"),
            "sql_hash": event.get("sql_hash"),
            "error_code": event.get("error_code"),
            "error_message": redact_text(event.get("error_message")),
            "repair_status": event.get("repair_status"),
            "repair_reason": event.get("repair_reason"),
            "repair_attempt_count": event.get("repair_attempt_count", 0),
            "repair_last_error": redact_text(event.get("repair_last_error")),
            "metadata_json": json.dumps(metadata, sort_keys=True, ensure_ascii=True),
        }
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO audit_log(audit_id,event_type,actor_type,actor_id,action,target_type,target_id,risk_level,status,created_at,updated_at,request_id,check_id,sql_hash,error_code,error_message,repair_status,repair_reason,repair_attempt_count,repair_last_error,metadata_json)
                VALUES (:audit_id,:event_type,:actor_type,:actor_id,:action,:target_type,:target_id,:risk_level,:status,:created_at,:updated_at,:request_id,:check_id,:sql_hash,:error_code,:error_message,:repair_status,:repair_reason,:repair_attempt_count,:repair_last_error,:metadata_json)
            """, record)
        return self.get_event(record["audit_id"])

    def update_event(self, audit_id: str, **updates: Any) -> dict[str, Any]:
        self.init()
        allowed = {"status", "error_code", "error_message", "repair_status", "repair_reason", "repair_attempt_count", "repair_last_error"}
        safe_updates = {key: redact_text(value) if key.endswith("error") or key == "error_message" else value for key, value in updates.items() if key in allowed}
        safe_updates["updated_at"] = now_iso()
        assignments = ", ".join(f"{key}=?" for key in safe_updates)
        with self.connect() as conn:
            conn.execute(f"UPDATE audit_log SET {assignments} WHERE audit_id=?", (*safe_updates.values(), audit_id))
        return self.get_event(audit_id)

    def get_event(self, audit_id: str) -> dict[str, Any]:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM audit_log WHERE audit_id=?", (audit_id,)).fetchone()
        if not row:
            raise AuditStoreError("PROFILE_NOT_FOUND", f"Audit event not found: {audit_id}")
        data = dict(row)
        data["metadata"] = json.loads(data.pop("metadata_json"))
        return data

    def list_events(self, limit: int = 50) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["metadata"] = json.loads(data.pop("metadata_json"))
            items.append(data)
        return items
