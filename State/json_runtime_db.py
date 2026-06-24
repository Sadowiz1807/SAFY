from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import uuid

from Logging.redact import redact_obj, redact_text
from State.runtime_db import RuntimeDBError, now_iso


SCHEMA_VERSION = 2

_ROW_KEYS = {"rows", "result_rows", "data_rows", "sample_rows", "records"}
_OMITTED_PAYLOAD_KEYS = {"rpc_response"}
_RESULT_CONTAINER_KEYS = {"chat_display", "query_result", "execute", "execution_result", "result", "payload", "data", "response", "rpc_response"}


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
            if key_text in _OMITTED_PAYLOAD_KEYS:
                result[key] = "<provider response omitted>"
            elif key_text in _ROW_KEYS or (child_result_container and _looks_like_row_list(item)):
                result[key] = "<display-only rows omitted>"
            else:
                result[key] = _strip_result_rows(item, in_result_container=child_result_container)
        return result
    if isinstance(value, list):
        if in_result_container and _looks_like_row_list(value):
            return "<display-only rows omitted>"
        return [_strip_result_rows(item, in_result_container=in_result_container) for item in value[:20]]
    return value


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "session": {}, "messages": [], "workspaces": [], "recovery_records": [], "locks": [], "agent_state": {}, "workflow_events": [], "tool_calls": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data.setdefault("schema_version", SCHEMA_VERSION)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True), encoding="utf-8")
    tmp.replace(path)


class JsonRuntimeDB:
    def __init__(self, sessions_dir: str | Path):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, chat_id: str) -> Path:
        raw = str(chat_id or "").strip()
        safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in raw)
        if not safe:
            safe = "session"
        if safe != raw or len(safe) > 80:
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
            safe = f"{safe[:64].rstrip('_-') or 'session'}_{digest}"
        return self.sessions_dir / f"session_{safe}.json"

    def init(self) -> None:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        pass

    def check_version(self, expected: int = SCHEMA_VERSION) -> int:
        self.init()
        for path in self.sessions_dir.glob("session_*.json"):
            version = int(_read(path).get("schema_version") or 1)
            if version != expected:
                raise RuntimeDBError(
                    "RUNTIME_SCHEMA_VERSION_MISMATCH",
                    f"JSON runtime schema version mismatch in {path.name}: expected {expected}, found {version}.",
                )
        return expected

    def record_provenance(self, object_id: str, object_type: str, source: str, created_by: str, stage: str = "Stage 2", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        chat_id = "provenance"; self.create_session(chat_id); path = self._path(chat_id); data = _read(path)
        rec = {"object_id": object_id, "object_type": object_type, "source": source, "created_by": created_by, "created_at": now_iso(), "stage": stage, "metadata": self._safe_metadata(metadata)}
        data.setdefault("provenance", []).append(rec); _write(path, data); return rec

    def get_provenance(self, object_id: str) -> dict[str, Any]:
        for path in self.sessions_dir.glob("session_*.json"):
            for rec in _read(path).get("provenance", []):
                if rec.get("object_id") == object_id: return rec
        raise RuntimeDBError("PROFILE_NOT_FOUND", f"Provenance object not found: {object_id}")

    def create_schema_snapshot(self, workspace_id: str, source: str, schema_hash: str, schema_json: dict[str, Any], metadata: dict[str, Any] | None = None, snapshot_id: str | None = None) -> dict[str, Any]:
        ws = self.get_workspace(workspace_id); path = self._path(ws["chat_id"]); data = _read(path)
        rec = {"snapshot_id": snapshot_id or f"snap_{uuid.uuid4().hex}", "workspace_id": workspace_id, "source": source, "schema_hash": schema_hash, "schema": schema_json, "created_at": now_iso(), "invalidated_at": None, "metadata": self._safe_metadata(metadata)}
        data.setdefault("schema_snapshots", []).append(rec); _write(path, data); return rec

    def get_schema_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        for path in self.sessions_dir.glob("session_*.json"):
            for rec in _read(path).get("schema_snapshots", []):
                if rec.get("snapshot_id") == snapshot_id: return rec
        raise RuntimeDBError("PROFILE_NOT_FOUND", f"Schema snapshot not found: {snapshot_id}")

    def invalidate_schema_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        for path in self.sessions_dir.glob("session_*.json"):
            data = _read(path)
            for rec in data.get("schema_snapshots", []):
                if rec.get("snapshot_id") == snapshot_id:
                    rec["invalidated_at"] = now_iso(); _write(path, data); return rec
        raise RuntimeDBError("PROFILE_NOT_FOUND", f"Schema snapshot not found: {snapshot_id}")

    def _safe_metadata(self, metadata: dict[str, Any] | None) -> dict[str, Any]:
        # Query result rows are display-only and must not become canonical session state, even nested under chat_display/query_result/execute.
        return redact_obj(_strip_result_rows(metadata or {}))

    def create_session(self, chat_id: str, status: str = "active", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        data = _read(self._path(chat_id)); stamp = now_iso()
        current = data.get("session", {})
        session_metadata = self._safe_metadata(metadata if metadata is not None else current.get("metadata", {}))
        data["session"] = {"chat_id": chat_id, "created_at": current.get("created_at", stamp), "status": status, "metadata": session_metadata}
        _write(self._path(chat_id), data)
        return self.get_session(chat_id)

    def get_session(self, chat_id: str) -> dict[str, Any]:
        data = _read(self._path(chat_id))
        if not data.get("session"):
            raise RuntimeDBError("SESSION_NOT_FOUND", f"Session not found: {chat_id}")
        return data["session"]

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        items=[]
        for path in sorted(self.sessions_dir.glob("session_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            data=_read(path); sess=data.get("session") or {}
            if sess:
                msgs=data.get("messages", [])
                if msgs: sess={**sess, "last_message_preview": msgs[-1].get("content_redacted")}
                items.append(sess)
        return items[:limit]

    def add_message(self, chat_id: str, role: str, content: str, audit_id: str | None = None, workspace_id: str | None = None, metadata: dict[str, Any] | None = None) -> str:
        self.create_session(chat_id)
        path=self._path(chat_id); data=_read(path); mid=f"msg_{uuid.uuid4().hex}"; stamp=now_iso()
        safe_metadata = self._safe_metadata(metadata)
        data.setdefault("messages", []).append({"message_id": mid, "chat_id": chat_id, "role": role, "content_redacted": redact_text(content), "audit_id": audit_id, "workspace_id": workspace_id, "created_at": stamp, "metadata": safe_metadata})
        _write(path,data); return mid

    def list_messages(self, chat_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return _read(self._path(chat_id)).get("messages", [])[:limit]

    def get_agent_state(self, chat_id: str) -> dict[str, Any]:
        data = _read(self._path(chat_id))
        return redact_obj(data.get("agent_state") or {})

    def update_agent_state(self, chat_id: str, state: dict[str, Any]) -> dict[str, Any]:
        self.create_session(chat_id)
        path = self._path(chat_id)
        data = _read(path)
        safe_state = redact_obj(_strip_result_rows(state or {}))
        data["agent_state"] = safe_state
        _write(path, data)
        return safe_state

    def clear_agent_state(self, chat_id: str) -> dict[str, Any]:
        self.create_session(chat_id)
        path = self._path(chat_id)
        data = _read(path)
        data["agent_state"] = {}
        _write(path, data)
        return {"chat_id": chat_id, "agent_state_cleared": True}
    def record_workflow_event(self, chat_id: str, stage: str, status: str = "ok", workflow_id: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.create_session(chat_id)
        path = self._path(chat_id)
        data = _read(path)
        rec = {"event_id": f"wf_evt_{uuid.uuid4().hex}", "chat_id": chat_id, "workflow_id": workflow_id, "stage": stage, "status": status, "created_at": now_iso(), "metadata": self._safe_metadata(metadata)}
        data.setdefault("workflow_events", []).append(rec)
        data["workflow_events"] = data["workflow_events"][-500:]
        _write(path, data)
        return rec

    def list_workflow_events(self, chat_id: str, limit: int = 100) -> list[dict[str, Any]]:
        events = _read(self._path(chat_id)).get("workflow_events", [])
        return list(reversed(events[-limit:]))

    def record_tool_call(self, chat_id: str, tool_name: str, status: str = "ok", workflow_id: str | None = None, risk_class: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.create_session(chat_id)
        path = self._path(chat_id)
        data = _read(path)
        rec = {"tool_call_id": f"tool_call_{uuid.uuid4().hex}", "chat_id": chat_id, "workflow_id": workflow_id, "tool_name": tool_name, "status": status, "risk_class": risk_class, "created_at": now_iso(), "metadata": self._safe_metadata(metadata)}
        data.setdefault("tool_calls", []).append(rec)
        data["tool_calls"] = data["tool_calls"][-500:]
        _write(path, data)
        return rec

    def list_tool_calls(self, chat_id: str, limit: int = 100) -> list[dict[str, Any]]:
        calls = _read(self._path(chat_id)).get("tool_calls", [])
        return list(reversed(calls[-limit:]))

    def delete_session(self, chat_id: str) -> dict[str, Any]:
        path = self._path(chat_id)
        data = _read(path)
        if not data.get("session"):
            raise RuntimeDBError("SESSION_NOT_FOUND", f"Session not found: {chat_id}")
        path.unlink(missing_ok=True)
        return {"chat_id": chat_id, "deleted": True}

    def register_workspace(self, workspace_id: str, chat_id: str, path_redacted: str, status: str = "active", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.create_session(chat_id)
        path=self._path(chat_id); data=_read(path)
        rec={"workspace_id": workspace_id, "chat_id": chat_id, "path_redacted": redact_text(path_redacted), "status": status, "created_at": now_iso(), "metadata": self._safe_metadata(metadata)}
        data.setdefault("workspaces", []).append(rec); _write(path,data); return rec

    def _all_workspaces(self):
        for path in self.sessions_dir.glob("session_*.json"):
            for item in _read(path).get("workspaces", []):
                yield path, item

    def get_workspace(self, workspace_id: str) -> dict[str, Any]:
        for _, item in self._all_workspaces():
            if item.get("workspace_id") == workspace_id: return item
        raise RuntimeDBError("WORKSPACE_NOT_FOUND", f"Workspace not found: {workspace_id}")

    def list_workspaces(self, chat_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        items=[]
        for path in self.sessions_dir.glob("session_*.json"):
            data=_read(path)
            for item in data.get("workspaces", []):
                if chat_id is None or item.get("chat_id") == chat_id: items.append(item)
        return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]

    def update_workspace_status(self, workspace_id: str, status: str) -> dict[str, Any]:
        for path, item in self._all_workspaces():
            if item.get("workspace_id") == workspace_id:
                data=_read(path)
                for rec in data.get("workspaces", []):
                    if rec.get("workspace_id") == workspace_id: rec["status"] = status; item = rec
                _write(path,data); return item
        raise RuntimeDBError("WORKSPACE_NOT_FOUND", f"Workspace not found: {workspace_id}")

    def session_timeline(self, chat_id: str, limit: int = 100) -> dict[str, Any]:
        return {"session": self.get_session(chat_id), "messages": self.list_messages(chat_id, limit), "workspaces": self.list_workspaces(chat_id, limit=limit)}

    def add_recovery_record(self, type: str, severity: str, status: str, summary: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        chat_id="recovery"; self.create_session(chat_id); path=self._path(chat_id); data=_read(path)
        rec={"recovery_id": f"rec_{uuid.uuid4().hex}", "type": type, "severity": severity, "status": status, "summary": redact_text(summary), "created_at": now_iso(), "updated_at": now_iso(), "metadata": self._safe_metadata(metadata)}
        data.setdefault("recovery_records", []).append(rec); _write(path,data); return rec

    def list_recovery_records(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        items=[]
        for path in self.sessions_dir.glob("session_*.json"):
            for rec in _read(path).get("recovery_records", []):
                if status is None or rec.get("status") == status: items.append(rec)
        return items[:limit]

    def get_recovery_record(self, recovery_id: str) -> dict[str, Any]:
        for rec in self.list_recovery_records(limit=10000):
            if rec.get("recovery_id") == recovery_id: return rec
        raise RuntimeDBError("RECOVERY_RECORD_NOT_FOUND", f"Recovery record not found: {recovery_id}")

    def update_recovery_status(self, recovery_id: str, status: str, summary: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        for path in self.sessions_dir.glob("session_*.json"):
            data=_read(path)
            for rec in data.get("recovery_records", []):
                if rec.get("recovery_id") == recovery_id:
                    rec["status"]=status; rec["updated_at"]=now_iso()
                    if summary: rec["summary"]=redact_text(summary)
                    if metadata is not None: rec["metadata"] = self._safe_metadata(metadata)
                    _write(path,data); return rec
        raise RuntimeDBError("RECOVERY_RECORD_NOT_FOUND", f"Recovery record not found: {recovery_id}")

    def acquire_workspace_lock(self, workspace_id: str, owner: str, reason: str, expires_at: str | None = None, metadata: dict[str, Any] | None = None, lock_id: str | None = None) -> dict[str, Any]:
        ws = self.get_workspace(workspace_id)
        path = self._path(ws["chat_id"]); data = _read(path)
        active = [lock for lock in data.get("locks", []) if lock.get("workspace_id") == workspace_id and lock.get("status") == "active" and lock.get("released_at") is None]
        if active:
            raise RuntimeDBError("WORKSPACE_LOCKED", f"Workspace is locked: {workspace_id}")
        rec = {"lock_id": lock_id or f"lock_{uuid.uuid4().hex}", "workspace_id": workspace_id, "owner": owner, "reason": reason, "status": "active", "created_at": now_iso(), "expires_at": expires_at, "released_at": None, "metadata": self._safe_metadata(metadata)}
        data.setdefault("locks", []).append(rec); _write(path, data); return rec

    def release_workspace_lock(self, lock_id: str) -> dict[str, Any]:
        for path in self.sessions_dir.glob("session_*.json"):
            data = _read(path)
            for lock in data.get("locks", []):
                if lock.get("lock_id") == lock_id:
                    lock["status"] = "released"; lock["released_at"] = now_iso(); _write(path, data); return lock
        raise RuntimeDBError("PROFILE_NOT_FOUND", f"Workspace lock not found: {lock_id}")

    def cleanup_workspace(self, workspace_id: str) -> dict[str, Any]:
        ws = self.get_workspace(workspace_id)
        data = _read(self._path(ws["chat_id"]))
        if any(lock.get("workspace_id") == workspace_id and lock.get("status") == "active" and lock.get("released_at") is None for lock in data.get("locks", [])):
            raise RuntimeDBError("WORKSPACE_ACTIVE_LOCKED", f"Workspace is locked: {workspace_id}")
        ws=self.update_workspace_status(workspace_id, "cleaned")
        self.add_recovery_record("workspace_cleanup", "low", "resolved", f"Workspace {workspace_id} marked cleaned.", {"workspace_id": workspace_id})
        return ws

    def recovery_scan(self) -> dict[str, Any]:
        return {"stale_locks_found": 0, "released_locks": [], "action": "released"}

    def recovery_resolve(self, recovery_id: str, action: str) -> dict[str, Any]:
        return self.update_recovery_status(recovery_id, "resolved" if action in {"cleanup", "restore"} else "abandoned", f"Recovery action {action} applied.", {"action": action})
