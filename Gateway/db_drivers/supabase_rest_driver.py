from __future__ import annotations

from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import os
import re
import time

from Gateway.sql_classifier import classify_sql

from .base import DEFAULT_ROW_LIMIT, SecretContext, is_sensitive_name, resolve_secret, success_envelope, user_execution_result
from .errors import DriverError

_SIMPLE_SELECT_RE = re.compile(
    r"^\s*select\s+(?P<columns>\*|[a-zA-Z0-9_.,\s\"]+)\s+from\s+(?P<table>[a-zA-Z_][\w.]*)"
    r"(?:\s+where\s+(?P<where>[a-zA-Z_][\w]*\s*=\s*('[^']*'|\d+(?:\.\d+)?)))?"
    r"(?:\s+order\s+by\s+(?P<order>[a-zA-Z_][\w]*)(?:\s+(?P<direction>asc|desc))?)?"
    r"(?:\s+limit\s+(?P<limit>\d+))?\s*;?\s*$",
    re.I,
)


def _clean_rpc_name(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "safy_execute_sql"
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", raw):
        raise DriverError("SUPABASE_RPC_NAME_INVALID", "Supabase SQL RPC function name is invalid.", {"rpc_function": raw})
    return raw


class SupabaseRpcDriver:
    """Supabase driver with a separate RPC execution transport.

    This driver intentionally does not pretend that Supabase is a direct
    PostgreSQL profile. Supabase profiles use base_url + API key, can read via
    PostgREST, and execute user-approved DDL/DML through an explicit Postgres
    function exposed at /rest/v1/rpc/<function>.
    """

    driver = "supabase_rpc"

    def _secret(self, profile: dict[str, Any], secret_context: SecretContext | None = None) -> str:
        secret = resolve_secret(profile, secret_context) or profile.get("api_key") or profile.get("password") or profile.get("raw_secret")
        if not secret:
            raise DriverError("DB_SECRET_MISSING", "Supabase API key is missing.")
        return str(secret)

    def _base_url(self, profile: dict[str, Any]) -> str:
        base_url = str(profile.get("base_url") or "").strip().rstrip("/")
        if not base_url:
            host = str(profile.get("host") or "").strip().rstrip("/")
            if host:
                if not host.startswith(("http://", "https://")):
                    host = "https://" + host
                base_url = host.rstrip("/")
        if base_url and "/rest/v1" not in base_url:
            base_url = base_url.rstrip("/") + "/rest/v1"
        if not base_url or "/rest/v1" not in base_url or "supabase.co" not in base_url.lower():
            raise DriverError("DB_BASE_URL_INVALID", "Supabase Base URL must point to https://<project>.supabase.co/rest/v1 or the Supabase project URL.")
        return base_url

    def _headers(self, profile: dict[str, Any], *, accept: str = "application/json") -> dict[str, str]:
        secret = self._secret(profile)
        return {
            "apikey": secret,
            "Authorization": f"Bearer {secret}",
            "Accept": accept,
        }

    def _request_json(
        self,
        profile: dict[str, Any],
        url: str,
        *,
        method: str = "GET",
        accept: str = "application/json",
        body: dict[str, Any] | None = None,
        operation: str = "request",
    ) -> tuple[Any, int]:
        headers = self._headers(profile, accept=accept)
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
            headers["Prefer"] = "return=representation"
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=30) as response:
                raw = response.read().decode("utf-8", errors="replace")
                status = int(getattr(response, "status", 200))
                return json.loads(raw) if raw else None, status
        except HTTPError as exc:
            raw = ""
            try:
                raw = exc.read().decode("utf-8", errors="replace")
            except Exception:
                raw = ""
            details: dict[str, Any] = {"status_code": exc.code, "operation": operation}
            parsed: Any = None
            if raw:
                try:
                    parsed = json.loads(raw)
                    details["response"] = parsed
                except json.JSONDecodeError:
                    details["response_text"] = raw[:1000]
            code = "DB_REQUEST_FAILED"
            message = f"Supabase RPC/REST returned HTTP {exc.code}."
            if exc.code in {401, 403}:
                code = "DB_AUTH_FAILED"
                message = f"Supabase authorization failed with HTTP {exc.code}."
            elif exc.code == 404:
                code = "DB_RESOURCE_NOT_FOUND"
                message = "Supabase REST endpoint or RPC function was not found."
            # PostgREST returns PGRST202 when an RPC function is missing from the schema cache.
            if operation == "execute_rpc" and (
                exc.code == 404
                or (isinstance(parsed, dict) and str(parsed.get("code") or "").upper() == "PGRST202")
                or "schema cache" in raw.lower()
            ):
                rpc_function = details.get("rpc_function") or "safy_execute_sql"
                raise DriverError(
                    "SUPABASE_RPC_NOT_INSTALLED",
                    f"Supabase SQL RPC function '{rpc_function}' is not installed or PostgREST schema cache has not reloaded.",
                    details,
                ) from exc
            raise DriverError(code, message, details) from exc
        except URLError as exc:
            raise DriverError("DB_CONNECTION_FAILED", f"Supabase connection failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise DriverError("DB_CONNECTION_TIMEOUT", "Supabase connection timed out.") from exc
        except json.JSONDecodeError as exc:
            raise DriverError("DB_RESPONSE_PARSE_ERROR", "Supabase returned non-JSON response.") from exc

    def _rpc_function(self, profile: dict[str, Any]) -> str:
        return _clean_rpc_name(
            profile.get("sql_rpc_function")
            or profile.get("write_rpc_function")
            or os.getenv("SAFY_SUPABASE_SQL_RPC_FUNCTION")
            or "safy_execute_sql"
        )

    def _rpc_argument(self, profile: dict[str, Any]) -> str:
        raw = str(profile.get("sql_rpc_argument") or os.getenv("SAFY_SUPABASE_SQL_RPC_ARGUMENT") or "sql").strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", raw):
            raise DriverError("SUPABASE_RPC_ARGUMENT_INVALID", "Supabase SQL RPC argument name is invalid.", {"rpc_argument": raw})
        return raw

    def test_connection(self, profile: dict[str, Any], secret_context: SecretContext | None = None) -> dict[str, Any]:
        self._secret(profile, secret_context)
        base = self._base_url(profile)
        data, status = self._request_json(profile, base + "/", operation="test_connection")
        return success_envelope(
            self.driver,
            profile,
            {
                "status_code": status,
                "provider": "supabase",
                "connection_kind": "supabase_rpc",
                "execution_transport": "postgrest_rpc",
                "rpc_function": self._rpc_function(profile),
            },
        )

    def get_schema(self, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        self._secret(profile, secret_context)
        base = self._base_url(profile)
        try:
            spec, status = self._request_json(profile, base + "/", accept="application/openapi+json, application/json", operation="schema_introspection")
        except DriverError:
            return success_envelope(self.driver, profile, {"database": base, "schemas": ["public"], "tables": [], "sample_rows_included": False}, warnings=["Supabase OpenAPI schema is unavailable."])
        tables: list[dict[str, Any]] = []
        definitions = spec.get("definitions") if isinstance(spec, dict) else None
        if isinstance(definitions, dict):
            for table_name, definition in sorted(definitions.items()):
                if not isinstance(definition, dict):
                    continue
                props = definition.get("properties") or {}
                required = set(definition.get("required") or [])
                columns = []
                for col_name, meta in sorted(props.items()):
                    meta = meta if isinstance(meta, dict) else {}
                    columns.append({
                        "name": col_name,
                        "data_type": meta.get("format") or meta.get("type") or "unknown",
                        "nullable": col_name not in required,
                        "primary_key": col_name == "id",
                        "sensitive": is_sensitive_name(col_name),
                    })
                tables.append({"schema": "public", "name": table_name, "type": "table", "columns": columns, "primary_keys": ["id"] if any(c["name"] == "id" for c in columns) else [], "foreign_keys": [], "indexes": [], "row_count_estimate": None})
        return success_envelope(self.driver, profile, {"database": base, "schemas": ["public"], "tables": tables, "sample_rows_included": False, "status_code": status})

    def execute_readonly(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        match = _SIMPLE_SELECT_RE.match(sql or "")
        if not match:
            raise DriverError("SUPABASE_SQL_REQUIRES_RPC", "Supabase API mode can only run simple SELECT through REST. Use the approved SQL RPC for arbitrary SQL after sandbox validation.")
        row_limit = int((options or {}).get("row_limit") or DEFAULT_ROW_LIMIT)
        limit = min(int(match.group("limit") or row_limit), row_limit)
        table = match.group("table").split(".")[-1]
        columns = match.group("columns").strip()
        params: dict[str, str] = {"limit": str(limit)}
        if columns != "*":
            cleaned = ",".join([c.strip().strip('"') for c in columns.split(",") if c.strip()])
            if cleaned:
                params["select"] = cleaned
        if match.group("where"):
            col, value = re.split(r"\s*=\s*", match.group("where"), maxsplit=1)
            value = value.strip().strip("'")
            params[col.strip()] = f"eq.{value}"
        if match.group("order"):
            direction = (match.group("direction") or "asc").lower()
            params["order"] = f"{match.group('order')}.{direction}"
        url = self._base_url(profile) + "/" + table + "?" + urlencode(params)
        started = time.perf_counter()
        data, status = self._request_json(profile, url, operation="execute_select")
        rows = data if isinstance(data, list) else []
        rows = rows[:limit]
        out_columns = sorted({key for row in rows if isinstance(row, dict) for key in row.keys()})
        metadata = {"execution_id": f"exec_supabase_rpc_read_{int(started * 1000000)}", "row_count": len(rows), "truncated": False, "execution_time_ms": int((time.perf_counter() - started) * 1000), "row_limit": limit, "read_only": True, "no_result_persistence": True, "status_code": status, "execution_transport": "postgrest_rest"}
        return success_envelope(self.driver, profile, metadata, columns=out_columns, rows=rows, row_count=len(rows), truncated=False)

    def execute_user_sql(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        classification = classify_sql(sql)
        if classification.is_read_only:
            return self.execute_readonly(sql, profile, secret_context, options)
        started = time.perf_counter()
        function = self._rpc_function(profile)
        argument = self._rpc_argument(profile)
        url = self._base_url(profile) + "/rpc/" + function
        try:
            data, status = self._request_json(profile, url, method="POST", body={argument: sql}, operation="execute_rpc")
        except DriverError as exc:
            if exc.error_code == "SUPABASE_RPC_NOT_INSTALLED":
                exc.details.setdefault("rpc_function", function)
                exc.details.setdefault("install_hint", "Create public.safy_execute_sql(sql text) in Supabase SQL Editor, then run: notify pgrst, 'reload schema';")
            raise
        if isinstance(data, dict) and data.get("success") is False:
            raise DriverError(
                "SUPABASE_RPC_EXECUTION_FAILED",
                str(data.get("error_message") or "Supabase SQL RPC reported execution failure."),
                {"rpc_function": function, "response": data, "statement_type": classification.statement_type},
            )
        payload = user_execution_result(self.driver, profile, started, row_count=0, statement_type=classification.statement_type)
        payload["metadata"].update({
            "status_code": status,
            "provider": "supabase",
            "connection_kind": "supabase_rpc",
            "execution_transport": "postgrest_rpc",
            "rpc_function": function,
            "rpc_response": data if isinstance(data, (dict, list)) else None,
        })
        payload["status"] = "executed"
        return payload


# Compatibility name for existing imports and stored profiles. The behavior is
# now Supabase RPC execution, not direct PostgreSQL and not REST-only write block.
SupabaseRestDriver = SupabaseRpcDriver
