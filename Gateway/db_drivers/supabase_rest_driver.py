from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import os
import re
import time

from Gateway.sql_classifier import classify_sql
from Gateway.sql_normalizer import normalize_sql

from .base import bounded_row_limit, DEFAULT_ROW_LIMIT, SecretContext, is_sensitive_name, resolve_secret, success_envelope, user_execution_result
from .errors import DriverError

_SIMPLE_SELECT_RE = re.compile(
    r"^\s*select\s+(?P<columns>\*|[a-zA-Z0-9_.,\s\"]+)\s+from\s+(?P<table>[a-zA-Z_][\w.]*)"
    r"(?:\s+where\s+(?P<where>[a-zA-Z_][\w]*\s*=\s*('[^']*'|\d+(?:\.\d+)?)))?"
    r"(?:\s+order\s+by\s+(?P<order>[a-zA-Z_][\w]*)(?:\s+(?P<direction>asc|desc))?)?"
    r"(?:\s+limit\s+(?P<limit>\d+))?\s*;?\s*$",
    re.I,
)
_OPENAPI_PK_TAG_RE = re.compile(r"<pk\s*/?>", re.I)
_OPENAPI_UNIQUE_TAG_RE = re.compile(r"<unique\s*/?>", re.I)
_OPENAPI_FK_TAG_RE = re.compile(r"<fk\b(?P<attrs>[^>]*)/?>", re.I)
_OPENAPI_FK_ATTR_RE = re.compile(r"(?P<name>table|column|schema)\s*=\s*['\"](?P<value>[^'\"]+)['\"]", re.I)
_OPENAPI_FK_TEXT_RE = re.compile(r"foreign\s+key\s+to\s+[`'\"]?(?:(?P<schema>[A-Za-z_][\w$]*)\.)?(?P<table>[A-Za-z_][\w$]*)\.(?P<column>[A-Za-z_][\w$]*)", re.I)


def _openapi_column_relationship(description: Any) -> dict[str, str] | None:
    text = str(description or "")
    tag_match = _OPENAPI_FK_TAG_RE.search(text)
    if tag_match:
        attrs = {match.group("name").lower(): match.group("value") for match in _OPENAPI_FK_ATTR_RE.finditer(tag_match.group("attrs"))}
        if attrs.get("table"):
            return {
                "schema": attrs.get("schema") or "public",
                "table": attrs["table"],
                "column": attrs.get("column") or "id",
            }
    text_match = _OPENAPI_FK_TEXT_RE.search(text)
    if text_match:
        return {
            "schema": text_match.group("schema") or "public",
            "table": text_match.group("table"),
            "column": text_match.group("column"),
        }
    return None



def _clean_rpc_name(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "safy_execute_sql"
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", raw):
        raise DriverError("SUPABASE_RPC_NAME_INVALID", "Supabase SQL RPC function name is invalid.", {"rpc_function": raw})
    return raw


def _unique_dollar_tag(prefix: str, text: str) -> str:
    index = 0
    while True:
        suffix = "" if index == 0 else f"_{index}"
        tag = f"${prefix}{suffix}$"
        if tag not in text:
            return tag
        index += 1


def _atomic_postgres_batch(statements: list[str]) -> str:
    """Wrap checked statements as one PostgreSQL DO command.

    The installed Supabase bridge accepts one dynamic SQL command. A DO block
    keeps a checked batch inside one database transaction while still executing
    each statement in order. User-supplied function/procedure/DO statements are
    blocked before this driver is reached.
    """
    source = "\n".join(statements)
    outer_tag = _unique_dollar_tag("safy_batch", source)
    commands: list[str] = []
    for index, statement in enumerate(statements, start=1):
        statement_tag = _unique_dollar_tag(f"safy_stmt_{index}", source)
        commands.append(f"  EXECUTE {statement_tag}{statement}{statement_tag};")
    return f"DO {outer_tag}\nBEGIN\n" + "\n".join(commands) + f"\nEND\n{outer_tag}"


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
        if not base_url:
            raise DriverError("DB_BASE_URL_INVALID", "Supabase Base URL is required.")

        parsed = urlparse(base_url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        valid_host = hostname == "supabase.co" or hostname.endswith(".supabase.co")
        if (
            parsed.scheme.lower() != "https"
            or not valid_host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            # Validate the parsed hostname rather than searching the raw URL.
            # A substring check would accept hosts such as
            # ``project.supabase.co.attacker.example`` and send the API key there.
            raise DriverError(
                "DB_BASE_URL_INVALID",
                "Supabase Base URL must use HTTPS and a *.supabase.co host without credentials, query, or fragment.",
            )

        path = parsed.path.rstrip("/")
        if not path:
            path = "/rest/v1"
        elif path != "/rest/v1":
            if path.endswith("/rest/v1"):
                pass
            else:
                raise DriverError("DB_BASE_URL_INVALID", "Supabase Base URL path must be /rest/v1 or the project root.")
        return f"https://{parsed.netloc}{path}"

    def _headers(self, profile: dict[str, Any], secret_context: SecretContext | None = None, *, accept: str = "application/json") -> dict[str, str]:
        secret = self._secret(profile, secret_context)
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
        secret_context: SecretContext | None = None,
    ) -> tuple[Any, int]:
        headers = self._headers(profile, secret_context, accept=accept)
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
                    if isinstance(parsed, dict):
                        for source_key, target_key in (
                            ("code", "provider_error_code"),
                            ("message", "provider_message"),
                            ("details", "provider_details"),
                            ("hint", "provider_hint"),
                        ):
                            if parsed.get(source_key) not in (None, ""):
                                details[target_key] = str(parsed[source_key])[:1000]
                except json.JSONDecodeError:
                    # Do not persist or return arbitrary provider response bodies.
                    parsed = None
            code = "DB_REQUEST_FAILED"
            message = f"Supabase RPC/REST returned HTTP {exc.code}."
            if exc.code in {401, 403}:
                code = "DB_AUTH_FAILED"
                message = f"Supabase authorization failed with HTTP {exc.code}."
            elif exc.code == 404:
                code = "DB_RESOURCE_NOT_FOUND"
                message = "Supabase REST endpoint or RPC function was not found."
            is_rpc_operation = operation in {"execute_rpc", "test_connection_rpc"}
            provider_code = str((parsed or {}).get("code") or "").upper() if isinstance(parsed, dict) else ""
            if is_rpc_operation and (
                exc.code == 404
                or provider_code == "PGRST202"
                or "schema cache" in raw.lower()
            ):
                rpc_function = details.get("rpc_function") or "safy_execute_sql"
                raise DriverError(
                    "SUPABASE_RPC_NOT_INSTALLED",
                    f"Supabase SQL RPC function '{rpc_function}' is not installed or PostgREST schema cache has not reloaded.",
                    details,
                ) from exc
            if is_rpc_operation and ("wrong_arg" in raw or "argument" in raw.lower() or "parameter" in raw.lower()):
                raise DriverError("SUPABASE_RPC_ARGUMENT_INVALID", "Supabase SQL RPC argument name is invalid for the configured function.", details) from exc
            if is_rpc_operation:
                raise DriverError("SUPABASE_RPC_CALL_FAILED", message, details) from exc
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
        function = self._rpc_function(profile)
        argument = self._rpc_argument(profile)
        try:
            data, status = self._request_json(
                profile,
                base + "/rpc/" + function,
                method="POST",
                body={argument: "SELECT 1 AS safy_test;"},
                operation="test_connection_rpc",
                secret_context=secret_context,
            )
        except DriverError as exc:
            if exc.error_code == "SUPABASE_RPC_NOT_INSTALLED":
                exc.details.setdefault("rpc_function", function)
            if exc.error_code in {"SUPABASE_RPC_FAILED", "SUPABASE_RPC_EXECUTION_FAILED"}:
                exc.error_code = "SUPABASE_RPC_CALL_FAILED"
            raise
        return success_envelope(
            self.driver,
            profile,
            {
                "status_code": status,
                "provider": "supabase",
                "connection_kind": "supabase_rpc",
                "execution_transport": "postgrest_rpc",
                "rpc_function": function,
                "rpc_argument": argument,
            },
        )

    def get_schema(self, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        self._secret(profile, secret_context)
        base = self._base_url(profile)
        try:
            spec, status = self._request_json(
                profile,
                base + "/",
                accept="application/openapi+json, application/json",
                operation="schema_introspection",
            )
        except DriverError:
            return success_envelope(
                self.driver,
                profile,
                {"database": base, "schemas": ["public"], "sample_rows_included": False},
                warnings=["Supabase OpenAPI schema is unavailable."],
                tables=[],
                relationships=[],
            )

        tables: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        definitions = spec.get("definitions") if isinstance(spec, dict) else None
        if isinstance(definitions, dict):
            for table_name, definition in sorted(definitions.items()):
                if not isinstance(definition, dict):
                    continue
                props = definition.get("properties") or {}
                required = set(definition.get("required") or [])
                columns: list[dict[str, Any]] = []
                foreign_keys: list[dict[str, Any]] = []
                unique_constraints: list[dict[str, Any]] = []
                primary_keys: list[str] = []

                for ordinal_position, (column_name, raw_meta) in enumerate(sorted(props.items()), start=1):
                    meta = raw_meta if isinstance(raw_meta, dict) else {}
                    description = str(meta.get("description") or "")
                    is_primary = bool(_OPENAPI_PK_TAG_RE.search(description)) or bool(meta.get("x-primary-key"))
                    is_unique = bool(_OPENAPI_UNIQUE_TAG_RE.search(description)) or bool(meta.get("x-unique"))
                    if is_primary:
                        primary_keys.append(column_name)
                    if is_unique:
                        unique_constraints.append({"name": None, "columns": [column_name]})

                    relationship = _openapi_column_relationship(description)
                    if not relationship and isinstance(meta.get("x-foreign-key"), dict):
                        raw_fk = meta["x-foreign-key"]
                        relationship = {
                            "schema": str(raw_fk.get("schema") or "public"),
                            "table": str(raw_fk.get("table") or ""),
                            "column": str(raw_fk.get("column") or "id"),
                        }
                    if relationship and relationship.get("table"):
                        constraint_name = f"fk_{table_name}_{column_name}_{relationship['table']}_{relationship['column']}"
                        foreign_keys.append({
                            "constraint_name": constraint_name,
                            "columns": [column_name],
                            "references_schema": relationship.get("schema") or "public",
                            "references_table": relationship["table"],
                            "references_columns": [relationship.get("column") or "id"],
                            "on_update": "NO ACTION",
                            "on_delete": "NO ACTION",
                            "cardinality": "many_to_one",
                            "metadata": {"source": "postgrest_openapi"},
                        })
                        relationships.append({
                            "id": constraint_name,
                            "relationship_type": "foreign_key",
                            "source_node_id": f"public.{table_name}",
                            "source_columns": [column_name],
                            "target_node_id": f"{relationship.get('schema') or 'public'}.{relationship['table']}",
                            "target_columns": [relationship.get("column") or "id"],
                            "constraint_name": constraint_name,
                            "cardinality": "many_to_one",
                            "on_update": "NO ACTION",
                            "on_delete": "NO ACTION",
                            "nullable": column_name not in required,
                            "evidence": "postgrest_openapi",
                            "confidence": 1.0,
                        })

                    columns.append({
                        "name": column_name,
                        "data_type": meta.get("format") or meta.get("type") or "unknown",
                        "nullable": column_name not in required,
                        "primary_key": is_primary,
                        "unique": is_unique,
                        "default": meta.get("default"),
                        "ordinal_position": ordinal_position,
                        "sensitive": is_sensitive_name(column_name),
                    })

                # Older PostgREST specs do not tag primary keys. Keep the prior
                # `id` fallback, but only after checking explicit metadata.
                if not primary_keys and any(column["name"] == "id" for column in columns):
                    primary_keys = ["id"]
                    for column in columns:
                        if column["name"] == "id":
                            column["primary_key"] = True

                tables.append({
                    "schema": "public",
                    "name": table_name,
                    "type": "table",
                    "columns": columns,
                    "primary_keys": primary_keys,
                    "unique_constraints": unique_constraints,
                    "foreign_keys": foreign_keys,
                    "indexes": [],
                    "row_count_estimate": None,
                })

        warnings: list[str] = []
        if tables and not relationships:
            warnings.append("PostgREST OpenAPI exposed table columns but no explicit foreign-key metadata; SAFY did not infer relationships from matching column names.")
        return success_envelope(
            self.driver,
            profile,
            {
                "database": base,
                "schemas": ["public"],
                "sample_rows_included": False,
                "status_code": status,
                "relationship_metadata": "postgrest_openapi",
            },
            warnings=warnings,
            tables=tables,
            relationships=relationships,
        )
    def _read_rpc_function(self, profile: dict[str, Any]) -> str | None:
        raw = str(profile.get("read_rpc_function") or os.getenv("SAFY_SUPABASE_READ_RPC_FUNCTION") or "").strip()
        if not raw:
            return None
        return _clean_rpc_name(raw)

    def _read_rpc_argument(self, profile: dict[str, Any]) -> str:
        raw = str(profile.get("read_rpc_argument") or profile.get("sql_rpc_argument") or "sql").strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", raw):
            raise DriverError("SUPABASE_RPC_ARGUMENT_INVALID", "Supabase read RPC argument name is invalid.", {"rpc_argument": raw})
        return raw

    def _execute_read_rpc(self, sql: str, profile: dict[str, Any], row_limit: int) -> dict[str, Any]:
        classification = classify_sql(sql)
        if not classification.is_read_only:
            raise DriverError("SUPABASE_REST_SQL_UNSUPPORTED", "Only read-only SQL can use Supabase read RPC.")
        function = self._read_rpc_function(profile)
        if not function:
            raise DriverError("SUPABASE_READ_RPC_NOT_CONFIGURED", "Complex Supabase read-only SQL requires a configured read RPC or a native PostgreSQL profile.")
        argument = self._read_rpc_argument(profile)
        started = time.perf_counter()
        try:
            data, status = self._request_json(profile, self._base_url(profile) + "/rpc/" + function, method="POST", body={argument: sql}, operation="execute_read_rpc")
        except DriverError as exc:
            raise DriverError("SUPABASE_READ_RPC_FAILED", "Supabase read RPC failed.", {"provider_error_code": exc.error_code, **exc.details}) from exc
        rows = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        rows = rows[:row_limit]
        columns = sorted({key for row in rows if isinstance(row, dict) for key in row.keys()})
        metadata = {"execution_id": f"exec_supabase_read_rpc_{int(started * 1000000)}", "row_count": len(rows), "truncated": False, "execution_time_ms": int((time.perf_counter() - started) * 1000), "row_limit": row_limit, "read_only": True, "no_result_persistence": True, "status_code": status, "execution_transport": "postgrest_read_rpc", "rpc_function": function}
        return success_envelope(self.driver, profile, metadata, columns=columns, rows=rows, row_count=len(rows), truncated=False)

    def execute_readonly(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        match = _SIMPLE_SELECT_RE.match(sql or "")
        row_limit = bounded_row_limit((options or {}).get("row_limit"), DEFAULT_ROW_LIMIT)
        if not match:
            return self._execute_read_rpc(sql, profile, row_limit)
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
        normalized = normalize_sql(sql)
        statements = normalized.statements
        if not statements:
            raise DriverError("SUPABASE_RPC_EXECUTION_FAILED", "SQL is empty.")
        classification = classify_sql(statements[0]) if len(statements) == 1 else None
        if len(statements) == 1 and classification and classification.is_read_only:
            return self.execute_readonly(statements[0], profile, secret_context, options)
        started = time.perf_counter()
        function = self._rpc_function(profile)
        argument = self._rpc_argument(profile)
        url = self._base_url(profile) + "/rpc/" + function
        rpc_sql = statements[0] if len(statements) == 1 else _atomic_postgres_batch(statements)
        try:
            data, status = self._request_json(profile, url, method="POST", body={argument: rpc_sql}, operation="execute_rpc")
        except DriverError as exc:
            if exc.error_code == "SUPABASE_RPC_NOT_INSTALLED":
                exc.details.setdefault("rpc_function", function)
                exc.details.setdefault("install_hint", "Create public.safy_execute_sql(sql text) in Supabase SQL Editor, then run: notify pgrst, 'reload schema';")
            raise
        if isinstance(data, dict) and data.get("success") is False:
            raise DriverError(
                "SUPABASE_RPC_EXECUTION_FAILED",
                str(data.get("error_message") or "Supabase SQL RPC reported execution failure."),
                {
                    "rpc_function": function,
                    "rpc_error_code": str(data.get("error_code") or "SUPABASE_RPC_EXECUTION_FAILED"),
                    "statement_type": classification.statement_type if classification else "BATCH",
                    "statement_count": len(statements),
                },
            )
        payload = user_execution_result(self.driver, profile, started, row_count=0, statement_type=classification.statement_type if classification else "BATCH")
        payload["metadata"].update({
            "status_code": status,
            "provider": "supabase",
            "connection_kind": "supabase_rpc",
            "execution_transport": "postgrest_rpc",
            "rpc_function": function,
            "rpc_status": str(data.get("status") or "executed") if isinstance(data, dict) else "executed",
            "statement_count": len(statements),
            "transactional_batch": len(statements) > 1,
        })
        payload["status"] = "executed"
        return payload


# Compatibility name for existing imports and stored profiles. The behavior is
# now Supabase RPC execution, not direct PostgreSQL and not REST-only write block.
SupabaseRestDriver = SupabaseRpcDriver
