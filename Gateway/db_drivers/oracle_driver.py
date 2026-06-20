from __future__ import annotations

from typing import Any
import time

from .base import DEFAULT_ROW_LIMIT, SecretContext, is_sensitive_name, query_result, resolve_secret, success_envelope
from .errors import DriverError


class OracleDriver:
    driver = "oracle"

    def _connect(self, profile: dict[str, Any], secret_context: SecretContext | None = None):
        try:
            import oracledb
        except Exception as exc:
            raise DriverError("DB_DRIVER_UNAVAILABLE", "python-oracledb is not installed. Install requirements-db.txt.") from exc
        password = resolve_secret(profile, secret_context)
        host = profile.get("host") or "127.0.0.1"
        port = int(profile.get("port") or 1521)
        service = profile.get("service_name") or profile.get("database") or "FREEPDB1"
        try:
            dsn = oracledb.makedsn(host, port, service_name=service)
            return oracledb.connect(user=profile.get("username") or None, password=password, dsn=dsn)
        except Exception as exc:
            raise DriverError("DB_CONNECTION_FAILED", str(exc)) from exc

    def test_connection(self, profile: dict[str, Any], secret_context: SecretContext | None = None) -> dict[str, Any]:
        conn = self._connect(profile, secret_context)
        try:
            cur = conn.cursor(); cur.execute("SELECT 1 FROM dual"); cur.fetchone()
            return success_envelope(self.driver, profile, {"service_name": profile.get("service_name") or profile.get("database"), "read_only": True, "mode": "thin_first"})
        finally:
            conn.close()

    def get_schema(self, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        conn = self._connect(profile, secret_context)
        owner_filter = str(profile.get("schema") or profile.get("username") or "").upper()
        try:
            cur = conn.cursor()
            if owner_filter:
                cur.execute("SELECT owner, table_name, num_rows FROM all_tables WHERE owner = :owner ORDER BY owner, table_name", owner=owner_filter)
            else:
                cur.execute("SELECT owner, table_name, num_rows FROM all_tables WHERE owner NOT IN ('SYS','SYSTEM') ORDER BY owner, table_name")
            tables = []
            for owner, table_name, num_rows in cur.fetchall():
                cur.execute("""
                    SELECT c.column_name, c.data_type, c.nullable,
                           CASE WHEN pk.column_name IS NULL THEN 0 ELSE 1 END AS is_pk
                    FROM all_tab_columns c
                    LEFT JOIN (
                      SELECT acc.owner, acc.table_name, acc.column_name
                      FROM all_constraints ac
                      JOIN all_cons_columns acc ON acc.owner=ac.owner AND acc.constraint_name=ac.constraint_name
                      WHERE ac.constraint_type='P'
                    ) pk ON pk.owner=c.owner AND pk.table_name=c.table_name AND pk.column_name=c.column_name
                    WHERE c.owner=:owner AND c.table_name=:table_name
                    ORDER BY c.column_id
                """, owner=owner, table_name=table_name)
                cols = [{"name": r[0], "data_type": r[1], "nullable": r[2] == "Y", "primary_key": bool(r[3]), "sensitive": is_sensitive_name(r[0])} for r in cur.fetchall()]
                tables.append({"schema": owner, "name": table_name, "type": "TABLE", "columns": cols, "primary_keys": [c["name"] for c in cols if c["primary_key"]], "foreign_keys": [], "indexes": [], "row_count_estimate": num_rows})
            return success_envelope(self.driver, profile, {"schemas": sorted({t["schema"] for t in tables}), "tables": tables, "sample_rows_included": False})
        finally:
            conn.close()

    def execute_readonly(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        row_limit = int((options or {}).get("row_limit") or DEFAULT_ROW_LIMIT)
        conn = self._connect(profile, secret_context)
        started = time.perf_counter()
        try:
            cur = conn.cursor(); cur.execute(sql)
            return query_result(self.driver, profile, cur, started, row_limit)
        finally:
            conn.close()
