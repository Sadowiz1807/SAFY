from __future__ import annotations

from typing import Any
import time

from .base import DEFAULT_ROW_LIMIT, SecretContext, is_sensitive_name, query_result, resolve_secret, success_envelope
from .errors import DriverError


class SQLServerDriver:
    driver = "sqlserver"

    def _connect(self, profile: dict[str, Any], secret_context: SecretContext | None = None):
        try:
            import pyodbc
        except Exception as exc:
            raise DriverError("DB_DRIVER_UNAVAILABLE", "pyodbc is not installed. Install requirements-db.txt.") from exc
        drivers = [d for d in pyodbc.drivers() if "ODBC Driver 18 for SQL Server" in d]
        if not drivers:
            raise DriverError("SQLSERVER_ODBC_DRIVER_MISSING", "Microsoft ODBC Driver 18 for SQL Server is not installed.")
        password = resolve_secret(profile, secret_context)
        parts = {
            "DRIVER": drivers[-1],
            "SERVER": f"{profile.get('host') or '127.0.0.1'},{int(profile.get('port') or 1433)}",
            "DATABASE": profile.get("database") or "",
            "UID": profile.get("username") or "",
            "PWD": password or "",
            "Encrypt": "yes" if profile.get("encrypt", True) else "no",
            "TrustServerCertificate": "yes" if profile.get("trust_server_certificate", False) else "no",
            "ApplicationIntent": "ReadOnly",
        }
        conn_str = ";".join(f"{k}={v}" for k, v in parts.items())
        try:
            conn = pyodbc.connect(conn_str, timeout=int(profile.get("timeout_seconds") or 10), autocommit=True)
            try:
                conn.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            except Exception:
                pass
            return conn
        except Exception as exc:
            raise DriverError("DB_CONNECTION_FAILED", str(exc)) from exc

    def test_connection(self, profile: dict[str, Any], secret_context: SecretContext | None = None) -> dict[str, Any]:
        conn = self._connect(profile, secret_context)
        try:
            conn.execute("SELECT 1").fetchone()
            return success_envelope(self.driver, profile, {"database": profile.get("database"), "read_only": True})
        finally:
            conn.close()

    def get_schema(self, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
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
            return success_envelope(self.driver, profile, {"database": profile.get("database"), "schemas": sorted({t["schema"] for t in tables}), "tables": tables, "sample_rows_included": False})
        finally:
            conn.close()

    def execute_readonly(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        row_limit = int((options or {}).get("row_limit") or DEFAULT_ROW_LIMIT)
        conn = self._connect(profile, secret_context)
        started = time.perf_counter()
        try:
            cur = conn.cursor()
            cur.execute(sql)
            return query_result(self.driver, profile, cur, started, row_limit)
        finally:
            conn.close()
