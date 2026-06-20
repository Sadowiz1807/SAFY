from __future__ import annotations
from typing import Any
import time
from .base import DEFAULT_ROW_LIMIT, SecretContext, query_result, resolve_secret, success_envelope, is_sensitive_name, user_execution_result
from .errors import DriverError
from Gateway.sql_classifier import classify_sql

class MySQLDriver:
    driver = "mysql"
    def _connect(self, profile: dict[str, Any], secret_context: SecretContext | None = None, read_only: bool = True):
        try:
            import pymysql
            import pymysql.cursors
        except Exception as exc:
            raise DriverError("DB_DRIVER_UNAVAILABLE", "pymysql is not installed. Install requirements-db.txt.") from exc
        password = resolve_secret(profile, secret_context)
        try:
            conn = pymysql.connect(host=profile.get("host") or "127.0.0.1", port=int(profile.get("port") or 3306), user=profile.get("username") or None, password=password, database=profile.get("database") or None, connect_timeout=5, read_timeout=int(profile.get("timeout_seconds") or 90), write_timeout=5, cursorclass=pymysql.cursors.DictCursor, autocommit=True)
            if read_only:
                with conn.cursor() as cur:
                    cur.execute("SET SESSION TRANSACTION READ ONLY")
            return conn
        except Exception as exc:
            raise DriverError("DB_CONNECTION_FAILED", str(exc)) from exc
    def test_connection(self, profile: dict[str, Any], secret_context: SecretContext | None = None) -> dict[str, Any]:
        conn=self._connect(profile, secret_context)
        try:
            with conn.cursor() as cur: cur.execute("SELECT 1")
            return success_envelope(self.driver, profile, {"database": profile.get("database"), "read_only": True})
        finally: conn.close()
    def get_schema(self, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        conn=self._connect(profile, secret_context); db=profile.get("database")
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT table_schema, table_name, table_type, table_rows FROM information_schema.tables WHERE table_schema=%s ORDER BY table_name", (db,))
                table_rows=cur.fetchall(); tables=[]
                for t in table_rows:
                    name=t["TABLE_NAME"] if "TABLE_NAME" in t else t["table_name"]
                    cur.execute("SELECT column_name, data_type, is_nullable, column_key FROM information_schema.columns WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position", (db,name))
                    cols=[{"name": c.get("COLUMN_NAME") or c.get("column_name"), "data_type": c.get("DATA_TYPE") or c.get("data_type"), "nullable": (c.get("IS_NULLABLE") or c.get("is_nullable")) == "YES", "primary_key": (c.get("COLUMN_KEY") or c.get("column_key")) == "PRI", "sensitive": is_sensitive_name(c.get("COLUMN_NAME") or c.get("column_name"))} for c in cur.fetchall()]
                    tables.append({"schema": db, "name": name, "type": t.get("TABLE_TYPE") or t.get("table_type"), "columns": cols, "primary_keys": [c["name"] for c in cols if c["primary_key"]], "foreign_keys": [], "indexes": [], "row_count_estimate": t.get("TABLE_ROWS") or t.get("table_rows")})
            return success_envelope(self.driver, profile, {"database": db, "schemas": [db], "tables": tables, "sample_rows_included": False})
        finally: conn.close()
    def execute_readonly(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        row_limit=int((options or {}).get("row_limit") or DEFAULT_ROW_LIMIT); conn=self._connect(profile, secret_context); started=time.perf_counter()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                return query_result(self.driver, profile, cur, started, row_limit)
        finally: conn.close()

    def execute_user_sql(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        row_limit=int((options or {}).get("row_limit") or DEFAULT_ROW_LIMIT)
        classification = classify_sql(sql)
        conn=self._connect(profile, secret_context, read_only=False)
        started=time.perf_counter()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                if cur.description:
                    return query_result(self.driver, profile, cur, started, row_limit)
                return user_execution_result(self.driver, profile, started, row_count=getattr(cur, "rowcount", 0), statement_type=classification.statement_type)
        finally:
            conn.close()
