from __future__ import annotations

from typing import Any
import re
import time

from .base import bounded_row_limit, DEFAULT_ROW_LIMIT, SecretContext, is_sensitive_name, query_result, resolve_secret, success_envelope, user_execution_result
from .errors import DriverError
from Gateway.sql_classifier import classify_sql
from Gateway.sql_normalizer import normalize_sql


SQLSERVER_SYSTEM_DATABASES = {"master", "model", "msdb", "tempdb"}
SQLSERVER_SYSTEM_SCHEMAS = {"sys", "information_schema"}


def is_system_database(dbms: str | None, database_name: str | None) -> bool:
    return str(dbms or "").lower() in {"sqlserver", "mssql", "sql_server"} and str(database_name or "").strip().lower() in SQLSERVER_SYSTEM_DATABASES


def filter_application_schema_objects(dbms: str | None, database_name: str | None, objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if is_system_database(dbms, database_name):
        return []
    return [obj for obj in objects if str(obj.get("schema") or "").lower() not in SQLSERVER_SYSTEM_SCHEMAS and not str(obj.get("name") or "").lower().startswith("spt_")]


def schema_cache_identity(profile: dict[str, Any]) -> str:
    return "|".join(str(profile.get(key) or "") for key in ("profile_id", "driver", "database", "profile_generation", "activation_generation", "context_generation"))


class SQLServerDriver:
    driver = "sqlserver"

    def _server_target(self, profile: dict[str, Any]) -> str:
        host = str(profile.get("host") or "127.0.0.1").strip()
        if host.lower().startswith("tcp:"):
            host = host[4:].strip()
        instance = str(profile.get("instance") or "").strip()
        port = int(profile.get("port") or 0)

        # A fixed TCP port is authoritative. Do not combine it with a named
        # instance because `host\instance,port` is ambiguous and caused SAFY to
        # route differently from the native Test Connection workflow.
        if port > 0:
            return f"tcp:{host},{port}"
        if instance:
            return f"{host}\\{instance}"
        return host

    @staticmethod
    def adapt_readonly_sql(sql: str) -> str:
        """Translate a bounded read query into SQL Server syntax.

        Models and users frequently submit PostgreSQL/MySQL ``LIMIT`` syntax in
        the Execute Box. Convert only a trailing LIMIT on a read-only SELECT/CTE
        so the checked SQL and the executed SQL remain identical.
        """
        text = (sql or "").strip()
        if not text or not re.match(r"^(SELECT|WITH)\b", text, re.I):
            return text

        had_semicolon = text.endswith(";")
        body = text[:-1].rstrip() if had_semicolon else text.rstrip()
        trailing = re.search(r"\s+LIMIT\s+(\d+)(?:\s+OFFSET\s+(\d+))?\s*$", body, re.I)
        if not trailing:
            return text

        limit = max(1, min(int(trailing.group(1)), 1000))
        offset = int(trailing.group(2) or 0)
        if offset:
            raise DriverError(
                "SQLSERVER_DIALECT_UNSUPPORTED",
                "SQL Server does not support LIMIT ... OFFSET. Use ORDER BY ... OFFSET ... ROWS FETCH NEXT ... ROWS ONLY.",
                {"driver": "sqlserver", "offset": offset, "limit": limit},
            )
        body = body[: trailing.start()].rstrip()

        if re.match(r"^\s*SELECT\s+(?:DISTINCT\s+)?TOP\s*(?:\(|\d)", body, re.I):
            return body + (";" if had_semicolon else "")

        select_match = re.match(r"^(\s*SELECT\s+)(DISTINCT\s+)?", body, re.I)
        if select_match:
            distinct = select_match.group(2) or ""
            rewritten = select_match.group(1) + distinct + f"TOP ({limit}) " + body[select_match.end():]
            return rewritten + ";"

        # Common CTE shape: WITH ... ) SELECT ... LIMIT n
        matches = list(re.finditer(r"\)\s*(SELECT\s+)(DISTINCT\s+)?", body, re.I))
        if matches:
            match = matches[-1]
            select_start = match.start(1)
            suffix = body[select_start:]
            if re.match(r"^SELECT\s+(?:DISTINCT\s+)?TOP\s*(?:\(|\d)", suffix, re.I):
                return body + (";" if had_semicolon else "")
            local_match = re.match(r"(SELECT\s+)(DISTINCT\s+)?", suffix, re.I)
            if local_match:
                distinct = local_match.group(2) or ""
                suffix = local_match.group(1) + distinct + f"TOP ({limit}) " + suffix[local_match.end():]
                return body[:select_start] + suffix + ";"

        raise DriverError(
            "SQLSERVER_DIALECT_UNSUPPORTED",
            "Could not safely translate LIMIT syntax for SQL Server. Replace LIMIT with TOP or OFFSET/FETCH.",
            {"driver": "sqlserver", "limit": limit},
        )

    @staticmethod
    def _execution_error(exc: Exception, *, operation: str) -> DriverError:
        message = str(exc)
        lowered = message.lower()
        details: dict[str, Any] = {"driver": "sqlserver", "operation": operation}
        if "invalid object name" in lowered or "(208)" in message:
            details["sql_server_error"] = 208
            return DriverError("SQLSERVER_OBJECT_NOT_FOUND", message, details)
        if "incorrect syntax" in lowered or "(102)" in message or "(156)" in message:
            details["sql_server_error"] = 102
            return DriverError("SQLSERVER_SYNTAX_ERROR", message, details)
        if "permission was denied" in lowered or "(229)" in message:
            details["sql_server_error"] = 229
            return DriverError("SQLSERVER_PERMISSION_DENIED", message, details)
        return DriverError("DB_QUERY_FAILED" if operation == "read" else "DB_EXECUTION_FAILED", message, details)

    @staticmethod
    def _connection_error(exc: Exception, authentication: str) -> DriverError:
        message = str(exc)
        lowered = message.lower()
        details: dict[str, Any] = {"authentication": authentication}
        if "18452" in message or "untrusted domain" in lowered:
            details["sql_server_error"] = 18452
            return DriverError(
                "SQLSERVER_UNTRUSTED_DOMAIN",
                "SQL Server rejected Windows Integrated Authentication because the login domain is not trusted.",
                details,
            )
        if "18456" in message or "login failed for user" in lowered:
            details["sql_server_error"] = 18456
            return DriverError(
                "SQLSERVER_LOGIN_FAILED",
                "SQL Server rejected the supplied login. Verify the saved username/password and authentication mode.",
                details,
            )
        if "10061" in message or "actively refused" in lowered:
            details["sql_server_error"] = 10061
            return DriverError(
                "SQLSERVER_CONNECTION_REFUSED",
                "SQL Server refused the TCP connection. Verify TCP/IP, host, port, and service state.",
                details,
            )
        return DriverError("DB_CONNECTION_FAILED", message, details)

    def _connection_string(self, profile: dict[str, Any], password: str | None, *, read_only: bool = True) -> str:
        driver = str(profile.get("odbc_driver") or "ODBC Driver 18 for SQL Server").strip()
        authentication = str(profile.get("authentication") or "sql_server").strip().lower()
        parts = {
            "DRIVER": driver,
            "SERVER": self._server_target(profile),
            "DATABASE": profile.get("database") or "",
            "Encrypt": "yes" if profile.get("encrypt", True) else "no",
            "TrustServerCertificate": "yes" if profile.get("trust_server_certificate", False) else "no",
            "ApplicationIntent": "ReadOnly" if read_only else "ReadWrite",
        }
        if authentication == "windows" or profile.get("trusted_connection"):
            parts["Trusted_Connection"] = "yes"
        else:
            parts["UID"] = profile.get("username") or ""
            parts["PWD"] = password or ""
        return ";".join(f"{key}={value}" for key, value in parts.items())

    def _connect(self, profile: dict[str, Any], secret_context: SecretContext | None = None, *, read_only: bool = True):
        try:
            import pyodbc
        except Exception as exc:
            raise DriverError("DB_DRIVER_UNAVAILABLE", "pyodbc is not installed. Install requirements-db.txt.") from exc
        requested_driver = str(profile.get("odbc_driver") or "ODBC Driver 18 for SQL Server").strip()
        available = pyodbc.drivers()
        if requested_driver not in available:
            raise DriverError(
                "SQLSERVER_ODBC_DRIVER_MISSING",
                f"Microsoft ODBC driver is not installed: {requested_driver}",
                {"requested_driver": requested_driver, "available_drivers": [item for item in available if "SQL Server" in item]},
            )
        password = resolve_secret(profile, secret_context)
        conn_str = self._connection_string(profile, password, read_only=read_only)
        try:
            # Read-only calls are independent and may autocommit. User-controlled
            # DDL/DML uses one explicit transaction and commits only after every
            # checked statement succeeds.
            conn = pyodbc.connect(
                conn_str,
                timeout=int(profile.get("timeout_seconds") or 10),
                autocommit=bool(read_only),
            )
            try:
                conn.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                if not read_only:
                    conn.execute("SET XACT_ABORT ON")
            except Exception:
                pass
            return conn
        except Exception as exc:
            raise self._connection_error(exc, authentication=str(profile.get("authentication") or "sql_server")) from exc

    def test_connection(self, profile: dict[str, Any], secret_context: SecretContext | None = None) -> dict[str, Any]:
        conn = self._connect(profile, secret_context)
        try:
            conn.execute("SELECT 1").fetchone()
            return success_envelope(self.driver, profile, {"database": profile.get("database"), "read_only": True})
        finally:
            conn.close()

    def get_schema(self, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        database_name = str(profile.get("database") or "").strip()
        if is_system_database(self.driver, database_name):
            raise DriverError(
                "SQLSERVER_SYSTEM_DATABASE_GROUNDING_BLOCKED",
                "SQL Server system databases cannot be used as application Schema Graph grounding. Select an application database first.",
                {"database": database_name, "driver": self.driver},
            )
        conn = self._connect(profile, secret_context)
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT s.name AS schema_name, t.name AS table_name, t.type_desc, p.rows AS row_count_estimate
                FROM sys.tables t
                JOIN sys.schemas s ON s.schema_id = t.schema_id
                LEFT JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1)
                ORDER BY s.name, t.name
            """)
            table_rows = cur.fetchall()
            tables = []
            for schema_name, table_name, type_desc, row_count in table_rows:
                cur.execute("""
                    SELECT c.name, ty.name, c.is_nullable,
                           CASE WHEN pk.column_id IS NULL THEN 0 ELSE 1 END AS is_pk
                    FROM sys.columns c
                    JOIN sys.types ty ON ty.user_type_id = c.user_type_id
                    LEFT JOIN (
                      SELECT ic.object_id, ic.column_id FROM sys.indexes i
                      JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
                      WHERE i.is_primary_key=1
                    ) pk ON pk.object_id=c.object_id AND pk.column_id=c.column_id
                    WHERE c.object_id = OBJECT_ID(?)
                    ORDER BY c.column_id
                """, f"[{schema_name}].[{table_name}]")
                cols = [{"name": r[0], "data_type": r[1], "nullable": bool(r[2]), "primary_key": bool(r[3]), "sensitive": is_sensitive_name(r[0])} for r in cur.fetchall()]
                tables.append({"schema": schema_name, "name": table_name, "type": type_desc, "columns": cols, "primary_keys": [c["name"] for c in cols if c["primary_key"]], "foreign_keys": [], "indexes": [], "row_count_estimate": row_count})
            tables = filter_application_schema_objects(self.driver, database_name, tables)
            return success_envelope(self.driver, profile, {"database": profile.get("database"), "schemas": sorted({t["schema"] for t in tables}), "tables": tables, "sample_rows_included": False})
        finally:
            conn.close()

    def execute_readonly(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        row_limit = bounded_row_limit((options or {}).get("row_limit"), DEFAULT_ROW_LIMIT)
        executable_sql = self.adapt_readonly_sql(sql)
        conn = self._connect(profile, secret_context)
        started = time.perf_counter()
        try:
            cur = conn.cursor()
            cur.execute(executable_sql)
            payload = query_result(self.driver, profile, cur, started, row_limit)
            payload.setdefault("executed_sql", executable_sql)
            return payload
        except DriverError:
            raise
        except Exception as exc:
            raise self._execution_error(exc, operation="read") from exc
        finally:
            conn.close()

    def execute_user_sql(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute sandbox-validated user DDL/DML in one SQL Server transaction."""
        row_limit = bounded_row_limit((options or {}).get("row_limit"), DEFAULT_ROW_LIMIT)
        normalized = normalize_sql(sql)
        statements = normalized.statements
        if not statements:
            raise DriverError("DB_EXECUTION_FAILED", "SQL is empty.")

        classification = classify_sql(statements[0]) if len(statements) == 1 else None
        conn = self._connect(profile, secret_context, read_only=False)
        started = time.perf_counter()
        try:
            cur = conn.cursor()
            if len(statements) == 1:
                cur.execute(statements[0])
                if cur.description:
                    payload = query_result(self.driver, profile, cur, started, row_limit)
                    conn.commit()
                    payload["metadata"].update({"read_only": False, "user_controlled": True})
                    return payload
                row_count = getattr(cur, "rowcount", 0)
                conn.commit()
                return user_execution_result(
                    self.driver,
                    profile,
                    started,
                    row_count=row_count,
                    statement_type=classification.statement_type if classification else "SQL",
                )

            total_row_count = 0
            for statement in statements:
                cur.execute(statement)
                row_count = getattr(cur, "rowcount", 0)
                if isinstance(row_count, int) and row_count > 0:
                    total_row_count += row_count
            conn.commit()
            payload = user_execution_result(
                self.driver,
                profile,
                started,
                row_count=total_row_count,
                statement_type="BATCH",
            )
            payload["metadata"].update({"statement_count": len(statements), "transactional_batch": True})
            return payload
        except DriverError:
            try:
                conn.rollback()
            finally:
                raise
        except Exception as exc:
            try:
                conn.rollback()
            finally:
                raise self._execution_error(exc, operation="write") from exc
        finally:
            conn.close()
