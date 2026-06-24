from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
import os
import re
import time
import uuid

from Logging.redact import redact_obj, redact_text
from .errors import DriverError

DEFAULT_ROW_LIMIT = 50
DEFAULT_TIMEOUT_SECONDS = 90
MAX_ROW_LIMIT = 1000
SENSITIVE_NAME_RE = re.compile(r"password|token|secret|email|phone|ssn|salary|dob|address|credit|card", re.I)

@dataclass(frozen=True)
class SecretContext:
    password: str | None = None

class ReadOnlyDriver(Protocol):
    driver: str
    def test_connection(self, profile: dict[str, Any], secret_context: SecretContext | None = None) -> dict[str, Any]: ...
    def get_schema(self, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]: ...
    def execute_readonly(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]: ...
    def execute_user_sql(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]: ...

def profile_id(profile: dict[str, Any]) -> str:
    return str(profile.get("profile_id") or profile.get("id") or "main_database")

def driver_name(profile: dict[str, Any]) -> str:
    return str(profile.get("driver") or profile.get("dbms") or "").lower()

def resolve_secret(profile: dict[str, Any], secret_context: SecretContext | None = None) -> str | None:
    if secret_context and secret_context.password:
        return secret_context.password
    # Runtime callers may materialize env-backed secrets into the profile just
    # before driver execution. This value is not persisted back to profile JSON.
    direct_secret = profile.get("password") or profile.get("api_key") or profile.get("raw_secret")
    if direct_secret:
        return str(direct_secret)
    env_name = profile.get("password_env")
    if not env_name:
        return None
    if not isinstance(env_name, str) or not env_name.replace("_", "").isalnum() or env_name.upper() != env_name:
        raise DriverError("DB_SECRET_ENV_INVALID", "Database password environment variable name is invalid.")
    return os.environ.get(env_name)

def success_envelope(driver: str, profile: dict[str, Any], metadata: dict[str, Any] | None = None, warnings: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    out = {"success": True, "driver": driver, "database_profile_id": profile_id(profile), "metadata": redact_obj(metadata or {}), "warnings": warnings or []}
    out.update(extra)
    return out

def error_envelope(exc: Exception, driver: str, profile: dict[str, Any]) -> dict[str, Any]:
    if isinstance(exc, DriverError):
        return exc.to_envelope(driver, profile_id(profile))
    return DriverError("DB_CONNECTION_FAILED", redact_text(str(exc))).to_envelope(driver, profile_id(profile))

def is_sensitive_name(name: str) -> bool:
    return bool(SENSITIVE_NAME_RE.search(name or ""))

def bounded_row_limit(value: Any, default: int = DEFAULT_ROW_LIMIT) -> int:
    """Normalize result limits at the driver boundary.

    API validation is the first line of defense, but drivers can also be called
    from internal workflows and tests. Keep every path within the same bounded
    range and reject neither malformed nor negative values by accidentally
    passing them to ``fetchmany``.
    """
    try:
        parsed = int(value) if value not in (None, "") else int(default)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(1, min(parsed, MAX_ROW_LIMIT))

def fetch_rows(cursor: Any, row_limit: int) -> tuple[list[str], list[dict[str, Any]], bool, int]:
    desc = cursor.description or []
    columns = [col[0] for col in desc]
    raw = cursor.fetchmany(row_limit + 1)
    truncated = len(raw) > row_limit
    raw = raw[:row_limit]
    rows: list[dict[str, Any]] = []
    for row in raw:
        if isinstance(row, dict):
            item = {col: row.get(col) for col in columns}
        else:
            item = {col: row[idx] for idx, col in enumerate(columns)}
        rows.append(redact_obj(item))
    return columns, rows, truncated, len(rows)

def query_result(driver: str, profile: dict[str, Any], cursor: Any, started: float, row_limit: int, warnings: list[str] | None = None) -> dict[str, Any]:
    columns, rows, truncated, row_count = fetch_rows(cursor, row_limit)
    metadata = {"execution_id": f"exec_{uuid.uuid4().hex}", "row_count": row_count, "truncated": truncated, "execution_time_ms": int((time.perf_counter() - started) * 1000), "row_limit": row_limit, "read_only": True, "no_result_persistence": True}
    return success_envelope(driver, profile, metadata, warnings, columns=columns, rows=rows, row_count=row_count, truncated=truncated)

def user_execution_result(driver: str, profile: dict[str, Any], started: float, *, row_count: int | None = None, statement_type: str | None = None, warnings: list[str] | None = None) -> dict[str, Any]:
    metadata = {
        "execution_id": f"exec_{uuid.uuid4().hex}",
        "row_count": row_count if row_count is not None and row_count >= 0 else 0,
        "execution_time_ms": int((time.perf_counter() - started) * 1000),
        "read_only": False,
        "user_controlled": True,
        "sandbox_precheck_required": True,
        "statement_type": statement_type,
    }
    return success_envelope(driver, profile, metadata, warnings or [], row_count=metadata["row_count"], rows=[], columns=[])
