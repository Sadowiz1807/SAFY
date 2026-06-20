
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import os
import re
import sqlite3
import time
import uuid

from Logging.redact import redact_text, redact_obj


@dataclass(frozen=True)
class ConnectionStatus:
    connected: bool
    dbms: str
    database: str | None = None
    host_redacted: str | None = None
    read_only: bool = True
    error_code: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class ReadonlyQueryResult:
    execution_id: str
    status: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    execution_time_ms: int
    row_limit: int
    read_only: bool = True
    result_ttl_seconds: int = 300
    no_result_persistence: bool = True


class AdapterError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(redact_text(message) or "Database adapter error.")

    def to_error(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self)}


class ConnectedDBAdapter:
    dbms = "generic"
    def __init__(self, profile: dict[str, Any], transient_password: str | None = None):
        self.profile = dict(profile)
        self.transient_password = transient_password
        self.conn = None

    def connect(self):
        raise NotImplementedError

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def test_connection(self) -> ConnectionStatus:
        try:
            self.connect()
            return ConnectionStatus(True, self.dbms, self.profile.get("database"), redact_host(self.profile.get("host")), True, message="Connected in read-only mode.")
        except AdapterError as exc:
            return ConnectionStatus(False, self.dbms, self.profile.get("database"), redact_host(self.profile.get("host")), True, exc.code, str(exc))
        finally:
            self.close()

    def introspect_schema(self) -> dict[str, Any]:
        raise NotImplementedError

    def execute_readonly(self, sql: str, params: dict[str, Any] | None = None, limits: dict[str, Any] | None = None) -> ReadonlyQueryResult:
        raise NotImplementedError


def redact_host(host: str | None) -> str | None:
    if not host:
        return None
    if host in {"localhost", "127.0.0.1", "::1"}:
        return host
    parts = str(host).split('.')
    return parts[0][:2] + "***" if len(parts) == 1 else parts[0][:2] + "***." + '.'.join(parts[1:])


def _sqlite_rows(conn: sqlite3.Connection, sql: str, row_limit: int) -> ReadonlyQueryResult:
    started = time.perf_counter()
    cur = conn.execute(sql)
    rows = [dict(row) for row in cur.fetchmany(row_limit + 1)]
    truncated = len(rows) > row_limit
    rows = rows[:row_limit]
    ms = int((time.perf_counter() - started) * 1000)
    columns = [item[0] for item in (cur.description or [])]
    return ReadonlyQueryResult(f"exec_real_{uuid.uuid4().hex}", "success", columns, redact_obj(rows), len(rows), truncated, ms, row_limit)


class FakeConnectedDBAdapter(ConnectedDBAdapter):
    dbms = "fake"
    def connect(self):
        self.conn = True
        return self.conn

    def introspect_schema(self) -> dict[str, Any]:
        self.connect()
        return {"dbms": self.dbms, "database": self.profile.get("database", "fake"), "tables": [{"name": "customers", "columns": [{"name": "id", "data_type": "integer", "primary_key": True}, {"name": "email", "data_type": "text", "sensitive": True}], "estimated_row_count": 2}], "sample_rows_included": False, "redacted": True}

    def execute_readonly(self, sql: str, params: dict[str, Any] | None = None, limits: dict[str, Any] | None = None) -> ReadonlyQueryResult:
        row_limit = int((limits or {}).get("row_limit", 100))
        rows = [{"id": 1, "email": "[REDACTED]"}, {"id": 2, "email": "[REDACTED]"}][:row_limit]
        return ReadonlyQueryResult(f"exec_fake_{uuid.uuid4().hex}", "success", ["id", "email"], rows, len(rows), False, 0, row_limit)


class SQLiteConnectedFileAdapter(ConnectedDBAdapter):
    dbms = "sqlite"
    def _path(self) -> Path:
        raw = self.profile.get("database") or self.profile.get("path")
        if not raw:
            raise AdapterError("DB_PROFILE_INVALID", "SQLite database path is required.")
        path = Path(raw).expanduser().resolve()
        root = self.profile.get("allowed_root")
        if root:
            root_path = Path(root).expanduser().resolve()
            if root_path != path and root_path not in path.parents:
                raise AdapterError("DB_PATH_NOT_ALLOWED", "SQLite database path is outside the configured allowed root.")
        return path

    def connect(self):
        path = self._path()
        if not path.exists():
            raise AdapterError("DB_CONNECTION_FAILED", f"SQLite database not found: {path}")
        try:
            self.conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
            self.conn.row_factory = sqlite3.Row
            return self.conn
        except sqlite3.Error as exc:
            raise AdapterError("DB_CONNECTION_FAILED", str(exc))

    def introspect_schema(self) -> dict[str, Any]:
        conn = self.connect()
        tables = []
        for row in conn.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            cols = []
            for col in conn.execute(f"PRAGMA table_info({quote_ident(row['name'])})"):
                cols.append({"name": col["name"], "data_type": col["type"], "nullable": not bool(col["notnull"]), "primary_key": bool(col["pk"]), "sensitive": is_sensitive_name(col["name"])})
            tables.append({"name": row["name"], "type": row["type"], "columns": cols, "estimated_row_count": None})
        return {"dbms": self.dbms, "database": str(self._path()), "tables": tables, "sample_rows_included": False, "redacted": True}

    def execute_readonly(self, sql: str, params: dict[str, Any] | None = None, limits: dict[str, Any] | None = None) -> ReadonlyQueryResult:
        conn = self.connect()
        return _sqlite_rows(conn, sql, int((limits or {}).get("row_limit", 100)))


def quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def is_sensitive_name(name: str) -> bool:
    return re.search(r"password|token|secret|email|phone|ssn|salary|dob|address", name or "", re.I) is not None



def _test_adapter_enabled() -> bool:
    return os.getenv("SAFY_ALLOW_FAKE_DB_ADAPTER", "0") == "1"

def adapter_for_profile(profile: dict[str, Any], transient_password: str | None = None) -> ConnectedDBAdapter:
    dbms = str(profile.get("dbms", "")).lower()
    if dbms == "fake":
        if not _test_adapter_enabled():
            raise AdapterError("FAKE_DB_ADAPTER_DISABLED", "The fake database adapter is disabled outside explicit test/dev runs.")
        return FakeConnectedDBAdapter(profile, transient_password)
    if dbms == "sqlite":
        return SQLiteConnectedFileAdapter(profile, transient_password)
    if dbms in {"mysql", "postgresql", "postgres"}:
        raise AdapterError("DB_DRIVER_UNAVAILABLE", f"{dbms} real adapter dependency is not installed in this SAFY runtime.")
    raise AdapterError("DBMS_UNSUPPORTED", f"Unsupported DBMS: {dbms}")
