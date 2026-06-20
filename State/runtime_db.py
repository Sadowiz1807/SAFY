from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import sqlite3
import uuid
from contextlib import closing

from Logging.redact import redact_obj, redact_text

SCHEMA_VERSION = 5


class RuntimeDBError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json(data: dict[str, Any] | None) -> str:
    return json.dumps(data or {}, sort_keys=True, ensure_ascii=True)


_ROW_KEYS = {"rows", "result_rows", "data_rows", "sample_rows", "records"}
_RESULT_CONTAINER_KEYS = {"chat_display", "query_result", "execute", "execution_result", "result", "payload", "data"}


def _looks_like_row_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, (dict, list, tuple)) for item in value[:20])


def _strip_result_rows(value: Any, *, in_result_container: bool = False) -> Any:
    if isinstance(value, dict):
        if value.get("type") == "query_result":
            in_result_container = True
        result = {}
        for key, item in value.items():
            key_text = str(key)
            child_result_container = in_result_container or key_text in _RESULT_CONTAINER_KEYS
            if key_text in _ROW_KEYS or (child_result_container and _looks_like_row_list(item)):
                result[key] = "<display-only rows omitted>"
            else:
                result[key] = _strip_result_rows(item, in_result_container=child_result_container)
        return result
    if isinstance(value, list):
        if in_result_container and _looks_like_row_list(value):
            return "<display-only rows omitted>"
        return [_strip_result_rows(item, in_result_container=in_result_container) for item in value[:20]]
    return value


def _safe_runtime_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    return redact_obj(_strip_result_rows(metadata or {}))


class RuntimeDB:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def close(self) -> None:
        # RuntimeDB opens short-lived connections, but callers can force SQLite
        # to release file handles before deleting temporary runtime directories.
        with closing(sqlite3.connect(self.path)):
            pass

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS schema_version(component TEXT PRIMARY KEY, version INTEGER NOT NULL, applied_at TEXT NOT NULL, notes TEXT);
            CREATE TABLE IF NOT EXISTS chat_runtime(chat_id TEXT PRIMARY KEY, current_workspace_id TEXT, last_workflow_id TEXT, workspace_status TEXT, target_dbms TEXT, execution_target TEXT, created_at TEXT, last_active_at TEXT, expires_at TEXT);
            CREATE TABLE IF NOT EXISTS chat_sessions(chat_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL, metadata_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS chat_messages(message_id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, role TEXT NOT NULL, content_redacted TEXT NOT NULL, audit_id TEXT, workspace_id TEXT, created_at TEXT NOT NULL, metadata_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS workspaces_registry(workspace_id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, path_redacted TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, metadata_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS recovery_records(recovery_id TEXT PRIMARY KEY, type TEXT NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL, summary TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, metadata_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS workflow_object_provenance(object_id TEXT PRIMARY KEY, object_type TEXT NOT NULL, source TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, stage TEXT NOT NULL, metadata_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS schema_snapshots(snapshot_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, source TEXT NOT NULL, schema_hash TEXT NOT NULL, schema_json TEXT NOT NULL, created_at TEXT NOT NULL, invalidated_at TEXT, metadata_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS workspace_locks(lock_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, owner TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT, released_at TEXT, metadata_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS agent_workflow_state(chat_id TEXT PRIMARY KEY, state_json TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS agent_workflow_events(event_id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, workflow_id TEXT, stage TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, metadata_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS agent_tool_calls(tool_call_id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, workflow_id TEXT, tool_name TEXT NOT NULL, status TEXT NOT NULL, risk_class TEXT, created_at TEXT NOT NULL, metadata_json TEXT NOT NULL);
            """)
            current = conn.execute("SELECT version FROM schema_version WHERE component='runtime'").fetchone()
            if current and current[0] > SCHEMA_VERSION:
                raise RuntimeDBError("RUNTIME_SCHEMA_VERSION_MISMATCH", "Runtime DB schema version is newer than this code.")
            conn.execute("INSERT OR REPLACE INTO schema_version(component, version, applied_at, notes) VALUES (?, ?, ?, ?)", ("runtime", SCHEMA_VERSION, now_iso(), "Stage 7 workflow events + tool trace + MCP-like agent state"))

    def check_version(self, expected: int = SCHEMA_VERSION) -> int:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT version FROM schema_version WHERE component='runtime'").fetchone()
        version = int(row[0])
        if version != expected:
            raise RuntimeDBError("RUNTIME_SCHEMA_VERSION_MISMATCH", "Runtime DB schema version mismatch.")
        return version

    def record_provenance(self, object_id: str, object_type: str, source: str, created_by: str, stage: str = "Stage 2", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.init()
        created_at = now_iso()
        with self.connect() as conn:
            conn.execute("INSERT INTO workflow_object_provenance VALUES (?, ?, ?, ?, ?, ?, ?)", (object_id, object_type, source, created_by, created_at, stage, _json(metadata)))
        return self.get_provenance(object_id)

    def get_provenance(self, object_id: str) -> dict[str, Any]:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM workflow_object_provenance WHERE object_id=?", (object_id,)).fetchone()
        if not row:
            raise RuntimeDBError("PROFILE_NOT_FOUND", f"Provenance object not found: {object_id}")
        data = dict(row)
        data["metadata"] = redact_obj(json.loads(data.pop("metadata_json")))
        return data

    def create_schema_snapshot(self, workspace_id: str, source: str, schema_hash: str, schema_json: dict[str, Any], metadata: dict[str, Any] | None = None, snapshot_id: str | None = None) -> dict[str, Any]:
        self.init()
        sid = snapshot_id or f"snap_{uuid.uuid4().hex}"
        with self.connect() as conn:
            conn.execute("INSERT INTO schema_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (sid, workspace_id, source, schema_hash, _json(schema_json), now_iso(), None, _json(metadata)))
        return self.get_schema_snapshot(sid)

    def get_schema_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM schema_snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
        if not row:
            raise RuntimeDBError("PROFILE_NOT_FOUND", f"Schema snapshot not found: {snapshot_id}")
        data = dict(row)
        data["schema"] = json.loads(data.pop("schema_json"))
        data["metadata"] = redact_obj(json.loads(data.pop("metadata_json")))
        return data

    def invalidate_schema_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        self.init()
        with self.connect() as conn:
            conn.execute("UPDATE schema_snapshots SET invalidated_at=? WHERE snapshot_id=?", (now_iso(), snapshot_id))
        return self.get_schema_snapshot(snapshot_id)

    def acquire_workspace_lock(self, workspace_id: str, owner: str, reason: str, expires_at: str | None = None, metadata: dict[str, Any] | None = None, lock_id: str | None = None) -> dict[str, Any]:
        self.init()
        current_time = now_iso()
        lid = lock_id or f"lock_{uuid.uuid4().hex}"
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            active = conn.execute("SELECT * FROM workspace_locks WHERE workspace_id=? AND status='active' AND released_at IS NULL AND (expires_at IS NULL OR expires_at > ?)", (workspace_id, current_time)).fetchone()
            if active:
                conn.rollback()
                raise RuntimeDBError("WORKSPACE_LOCKED", f"Workspace is locked: {workspace_id}")
            conn.execute("INSERT INTO workspace_locks VALUES (?, ?, ?, ?, 'active', ?, ?, NULL, ?)", (lid, workspace_id, owner, reason, current_time, expires_at, _json(metadata)))
            conn.commit()
        finally:
            conn.close()
        return self.get_workspace_lock(lid)

    def get_workspace_lock(self, lock_id: str) -> dict[str, Any]:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM workspace_locks WHERE lock_id=?", (lock_id,)).fetchone()
        if not row:
            raise RuntimeDBError("PROFILE_NOT_FOUND", f"Workspace lock not found: {lock_id}")
        data = dict(row)
        data["metadata"] = redact_obj(json.loads(data.pop("metadata_json")))
        return data

    def release_workspace_lock(self, lock_id: str) -> dict[str, Any]:
        self.init()
        with self.connect() as conn:
            conn.execute("UPDATE workspace_locks SET status='released', released_at=? WHERE lock_id=? AND released_at IS NULL", (now_iso(), lock_id))
        return self.get_workspace_lock(lock_id)

    def create_session(self, chat_id: str, status: str = "active", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.init()
        created_at = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_sessions VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    created_at=excluded.created_at,
                    status=excluded.status,
                    metadata_json=excluded.metadata_json
                """,
                (chat_id, created_at, status, _json(_safe_runtime_metadata(metadata))),
            )
        return self.get_session(chat_id)

    def get_session(self, chat_id: str) -> dict[str, Any]:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM chat_sessions WHERE chat_id=?", (chat_id,)).fetchone()
        if not row:
            raise RuntimeDBError("SESSION_NOT_FOUND", f"Session not found: {chat_id}")
        data = dict(row)
        data["metadata"] = redact_obj(json.loads(data.pop("metadata_json")))
        return data

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT s.*, 
                (SELECT content_redacted FROM chat_messages WHERE chat_id=s.chat_id ORDER BY created_at DESC LIMIT 1) as last_message_preview
                FROM chat_sessions s 
                ORDER BY s.created_at DESC LIMIT ?
            """, (limit,)).fetchall()
        items = []
        for row in rows:
            data = dict(row)
            data["metadata"] = redact_obj(json.loads(data.pop("metadata_json")))
            items.append(data)
        return items

    def add_message(self, chat_id: str, role: str, content: str, audit_id: str | None = None, workspace_id: str | None = None, metadata: dict[str, Any] | None = None) -> str:
        self.init()
        mid = f"msg_{uuid.uuid4().hex}"
        created_at = now_iso()
        content_redacted = redact_text(content)
        with self.connect() as conn:
            conn.execute("INSERT INTO chat_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (mid, chat_id, role, content_redacted, audit_id, workspace_id, created_at, _json(_safe_runtime_metadata(metadata))))
        return mid

    def list_messages(self, chat_id: str, limit: int = 100) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM chat_messages WHERE chat_id=? ORDER BY created_at ASC LIMIT ?", (chat_id, limit)).fetchall()
        items = []
        for row in rows:
            data = dict(row)
            data["metadata"] = redact_obj(json.loads(data.pop("metadata_json")))
            items.append(data)
        return items

    def get_agent_state(self, chat_id: str) -> dict[str, Any]:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT state_json FROM agent_workflow_state WHERE chat_id=?", (chat_id,)).fetchone()
        if not row:
            return {}
        return redact_obj(json.loads(row[0]))

    def update_agent_state(self, chat_id: str, state: dict[str, Any]) -> dict[str, Any]:
        self.init()
        self.create_session(chat_id)
        safe_state = redact_obj(_strip_result_rows(state or {}))
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO agent_workflow_state(chat_id, state_json, updated_at) VALUES (?, ?, ?)",
                (chat_id, json.dumps(safe_state, ensure_ascii=True, sort_keys=True), now_iso()),
            )
        return safe_state

    def clear_agent_state(self, chat_id: str) -> dict[str, Any]:
        self.init()
        with self.connect() as conn:
            conn.execute("DELETE FROM agent_workflow_state WHERE chat_id=?", (chat_id,))
        return {"chat_id": chat_id, "agent_state_cleared": True}
    def record_workflow_event(self, chat_id: str, stage: str, status: str = "ok", workflow_id: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.init()
        self.create_session(chat_id)
        event_id = f"wf_evt_{uuid.uuid4().hex}"
        created_at = now_iso()
        safe_metadata = redact_obj(metadata or {})
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO agent_workflow_events VALUES (?, ?, ?, ?, ?, ?, ?)",
                (event_id, chat_id, workflow_id, stage, status, created_at, _json(safe_metadata)),
            )
        return {"event_id": event_id, "chat_id": chat_id, "workflow_id": workflow_id, "stage": stage, "status": status, "created_at": created_at, "metadata": safe_metadata}

    def list_workflow_events(self, chat_id: str, limit: int = 100) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM agent_workflow_events WHERE chat_id=? ORDER BY created_at DESC LIMIT ?", (chat_id, limit)).fetchall()
        items = []
        for row in rows:
            data = dict(row)
            data["metadata"] = redact_obj(json.loads(data.pop("metadata_json")))
            items.append(data)
        return items

    def record_tool_call(self, chat_id: str, tool_name: str, status: str = "ok", workflow_id: str | None = None, risk_class: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.init()
        self.create_session(chat_id)
        tool_call_id = f"tool_call_{uuid.uuid4().hex}"
        created_at = now_iso()
        safe_metadata = redact_obj(metadata or {})
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO agent_tool_calls VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (tool_call_id, chat_id, workflow_id, tool_name, status, risk_class, created_at, _json(safe_metadata)),
            )
        return {"tool_call_id": tool_call_id, "chat_id": chat_id, "workflow_id": workflow_id, "tool_name": tool_name, "status": status, "risk_class": risk_class, "created_at": created_at, "metadata": safe_metadata}

    def list_tool_calls(self, chat_id: str, limit: int = 100) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM agent_tool_calls WHERE chat_id=? ORDER BY created_at DESC LIMIT ?", (chat_id, limit)).fetchall()
        items = []
        for row in rows:
            data = dict(row)
            data["metadata"] = redact_obj(json.loads(data.pop("metadata_json")))
            items.append(data)
        return items

    def add_recovery_record(self, type: str, severity: str, status: str, summary: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.init()
        rid = f"rec_{uuid.uuid4().hex}"
        now = now_iso()
        with self.connect() as conn:
            conn.execute("INSERT INTO recovery_records VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (rid, type, severity, status, redact_text(summary), now, now, _json(metadata)))
        return self.get_recovery_record(rid)

    def update_recovery_status(self, recovery_id: str, status: str, summary: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.init()
        now = now_iso()
        with self.connect() as conn:
            if summary:
                conn.execute("UPDATE recovery_records SET status=?, summary=?, updated_at=?, metadata_json=? WHERE recovery_id=?", (status, redact_text(summary), now, _json(metadata), recovery_id))
            else:
                conn.execute("UPDATE recovery_records SET status=?, updated_at=? WHERE recovery_id=?", (status, now, recovery_id))
        return self.get_recovery_record(recovery_id)

    def get_recovery_record(self, recovery_id: str) -> dict[str, Any]:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM recovery_records WHERE recovery_id=?", (recovery_id,)).fetchone()
        if not row:
            raise RuntimeDBError("RECOVERY_RECORD_NOT_FOUND", f"Recovery record not found: {recovery_id}")
        data = dict(row)
        data["summary"] = redact_text(data.get("summary", ""))
        data["metadata"] = redact_obj(json.loads(data.pop("metadata_json")))
        return data

    def list_recovery_records(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            if status:
                rows = conn.execute("SELECT * FROM recovery_records WHERE status=? ORDER BY updated_at DESC LIMIT ?", (status, limit)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM recovery_records ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        items = []
        for row in rows:
            data = dict(row)
            data["summary"] = redact_text(data.get("summary", ""))
            data["metadata"] = redact_obj(json.loads(data.pop("metadata_json")))
            items.append(data)
        return items

    def register_workspace(self, workspace_id: str, chat_id: str, path_redacted: str, status: str = "active", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.init()
        created_at = now_iso()
        with self.connect() as conn:
            conn.execute("INSERT INTO workspaces_registry VALUES (?, ?, ?, ?, ?, ?)", (workspace_id, chat_id, path_redacted, status, created_at, _json(metadata)))
        return self.get_workspace(workspace_id)

    def get_workspace(self, workspace_id: str) -> dict[str, Any]:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM workspaces_registry WHERE workspace_id=?", (workspace_id,)).fetchone()
        if not row:
            raise RuntimeDBError("WORKSPACE_NOT_FOUND", f"Workspace not found: {workspace_id}")
        data = dict(row)
        data["metadata"] = redact_obj(json.loads(data.pop("metadata_json")))
        return data

    def list_workspaces(self, chat_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            if chat_id:
                rows = conn.execute("SELECT * FROM workspaces_registry WHERE chat_id=? ORDER BY created_at DESC LIMIT ?", (chat_id, limit)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM workspaces_registry ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        items = []
        for row in rows:
            data = dict(row)
            data["metadata"] = redact_obj(json.loads(data.pop("metadata_json")))
            items.append(data)
        return items

    def update_workspace_status(self, workspace_id: str, status: str) -> dict[str, Any]:
        self.init()
        with self.connect() as conn:
            conn.execute("UPDATE workspaces_registry SET status=? WHERE workspace_id=?", (status, workspace_id))
        return self.get_workspace(workspace_id)


    def session_timeline(self, chat_id: str, limit: int = 100) -> dict[str, Any]:
        self.init()
        session = self.get_session(chat_id)
        messages = self.list_messages(chat_id, limit=limit)
        workspaces = self.list_workspaces(chat_id=chat_id, limit=limit)
        return {"session": session, "messages": messages, "workspaces": workspaces}

    def cleanup_workspace(self, workspace_id: str) -> dict[str, Any]:
        self.init()
        current_time = now_iso()
        with self.connect() as conn:
            active = conn.execute(
                "SELECT lock_id FROM workspace_locks WHERE workspace_id=? AND status='active' AND released_at IS NULL AND (expires_at IS NULL OR expires_at > ?)",
                (workspace_id, current_time),
            ).fetchone()
        if active:
            raise RuntimeDBError("WORKSPACE_ACTIVE_LOCKED", f"Workspace is locked: {workspace_id}")
        workspace = self.update_workspace_status(workspace_id, "cleaned")
        self.add_recovery_record(
            type="workspace_cleanup",
            severity="low",
            status="resolved",
            summary=f"Workspace {workspace_id} marked cleaned.",
            metadata={"workspace_id": workspace_id},
        )
        return workspace

    def recovery_scan(self) -> dict[str, Any]:
        stale_locks = self.find_stale_locks()
        released = []
        for lock in stale_locks:
            released.append(self.release_workspace_lock(lock["lock_id"]))
        if released:
            self.add_recovery_record(
                type="stale_workspace_locks",
                severity="medium",
                status="resolved",
                summary=f"Released {len(released)} stale workspace lock(s).",
                metadata={"released_lock_ids": [lock["lock_id"] for lock in released]},
            )
        return {"stale_locks_found": len(stale_locks), "released_locks": released, "action": "released"}

    def recovery_resolve(self, recovery_id: str, action: str) -> dict[str, Any]:
        if action not in {"cleanup", "restore", "abandon"}:
            raise RuntimeDBError("RECOVERY_ACTION_INVALID", f"Unsupported recovery action: {action}")
        status = "resolved" if action in {"cleanup", "restore"} else "abandoned"
        summary = f"Recovery action {action} applied."
        return self.update_recovery_status(recovery_id, status=status, summary=summary, metadata={"action": action})

    def find_stale_locks(self, expiration_minutes: int = 60) -> list[dict[str, Any]]:
        self.init()
        # In a real system we'd check if the PID is still alive. 
        # Here we'll just check by time as a heuristic for the recovery.
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM workspace_locks WHERE status='active' AND released_at IS NULL AND created_at < datetime('now', ?)", (f'-{expiration_minutes} minutes',)).fetchall()
        return [dict(row) for row in rows]
