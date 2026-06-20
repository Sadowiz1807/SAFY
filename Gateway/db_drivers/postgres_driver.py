from __future__ import annotations
from typing import Any
import time
from .base import DEFAULT_ROW_LIMIT, SecretContext, query_result, resolve_secret, success_envelope, is_sensitive_name, user_execution_result
from .errors import DriverError
from Gateway.sql_classifier import classify_sql

class PostgresDriver:
    driver = "postgresql"
    def _connect(self, profile: dict[str, Any], secret_context: SecretContext | None = None, read_only: bool = True):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except Exception as exc:
            raise DriverError("DB_DRIVER_UNAVAILABLE", "psycopg v3 is not installed. Install requirements-db.txt.") from exc
        password=resolve_secret(profile, secret_context)
        try:
            conn=psycopg.connect(host=profile.get("host") or "127.0.0.1", port=int(profile.get("port") or 5432), dbname=profile.get("database"), user=profile.get("username") or None, password=password, connect_timeout=5, row_factory=dict_row)
            conn.autocommit=True
            if read_only:
                conn.read_only=True
            return conn
        except Exception as exc:
            raise DriverError("DB_CONNECTION_FAILED", str(exc)) from exc
    def test_connection(self, profile: dict[str, Any], secret_context: SecretContext | None = None) -> dict[str, Any]:
        conn=self._connect(profile, secret_context)
        try:
            conn.execute("SELECT 1").fetchone()
            return success_envelope(self.driver, profile, {"database": profile.get("database"), "read_only": True})
        finally: conn.close()
    def get_schema(self, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        conn=self._connect(profile, secret_context)
        try:
            tables=[]
            table_rows=conn.execute("SELECT table_schema, table_name, table_type FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY table_schema, table_name").fetchall()
            for t in table_rows:
                schema=t['table_schema']; name=t['table_name']
                cols=[{"name": c['column_name'], "data_type": c['data_type'], "nullable": c['is_nullable'] == 'YES', "primary_key": False, "sensitive": is_sensitive_name(c['column_name'])} for c in conn.execute("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position", (schema,name)).fetchall()]
                pk_rows=conn.execute("SELECT kcu.column_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name=kcu.constraint_name AND tc.table_schema=kcu.table_schema WHERE tc.constraint_type='PRIMARY KEY' AND tc.table_schema=%s AND tc.table_name=%s", (schema,name)).fetchall()
                pks={r['column_name'] for r in pk_rows}
                for c in cols: c['primary_key']=c['name'] in pks
                tables.append({"schema": schema, "name": name, "type": t['table_type'], "columns": cols, "primary_keys": list(pks), "foreign_keys": [], "indexes": [], "row_count_estimate": None})
            return success_envelope(self.driver, profile, {"database": profile.get("database"), "schemas": sorted({t['schema'] for t in tables}), "tables": tables, "sample_rows_included": False})
        finally: conn.close()
    def execute_readonly(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        row_limit=int((options or {}).get("row_limit") or DEFAULT_ROW_LIMIT); conn=self._connect(profile, secret_context); started=time.perf_counter()
        try:
            cur=conn.execute(sql)
            return query_result(self.driver, profile, cur, started, row_limit)
        finally: conn.close()

    def execute_user_sql(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        row_limit=int((options or {}).get("row_limit") or DEFAULT_ROW_LIMIT)
        classification = classify_sql(sql)
        conn=self._connect(profile, secret_context, read_only=False)
        started=time.perf_counter()
        try:
            cur=conn.execute(sql)
            if cur.description:
                return query_result(self.driver, profile, cur, started, row_limit)
            return user_execution_result(self.driver, profile, started, row_count=getattr(cur, "rowcount", 0), statement_type=classification.statement_type)
        finally:
            conn.close()
