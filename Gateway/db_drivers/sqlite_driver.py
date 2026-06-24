from __future__ import annotations

from pathlib import Path
from typing import Any
import sqlite3
import time

from .base import bounded_row_limit, DEFAULT_ROW_LIMIT, SecretContext, is_sensitive_name, query_result, success_envelope, profile_id, user_execution_result
from .errors import DriverError
from Gateway.sql_classifier import classify_sql
from Gateway.sql_normalizer import normalize_sql

class SQLiteDriver:
    driver = "sqlite"

    def _path(self, profile: dict[str, Any]) -> Path:
        raw = profile.get("database") or profile.get("path")
        if not raw:
            raise DriverError("DB_PROFILE_INVALID", "SQLite database path is required.")
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            raise DriverError("DB_CONNECTION_FAILED", "SQLite database file does not exist.")
        allowed_root = profile.get("allowed_root")
        if allowed_root:
            root = Path(allowed_root).expanduser().resolve()
            if path != root and root not in path.parents:
                raise DriverError("DB_PATH_NOT_ALLOWED", "SQLite path is outside the allowed root.")
        return path

    def _connect(self, profile: dict[str, Any], read_only: bool = True) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self._path(profile)}?mode={'ro' if read_only else 'rw'}", uri=True, timeout=2)
        conn.row_factory = sqlite3.Row
        return conn

    def test_connection(self, profile: dict[str, Any], secret_context: SecretContext | None = None) -> dict[str, Any]:
        with self._connect(profile) as conn:
            conn.execute("SELECT 1").fetchone()
        return success_envelope(self.driver, profile, {"database": str(self._path(profile)), "read_only": True})

    def get_schema(self, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._connect(profile) as conn:
            tables=[]
            for table in conn.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name"):
                name=table["name"]
                cols=[]
                for col in conn.execute('PRAGMA table_info("' + name.replace('"','""') + '")'):
                    cols.append({"name": col["name"], "data_type": col["type"], "nullable": not bool(col["notnull"]), "primary_key": bool(col["pk"]), "sensitive": is_sensitive_name(col["name"])})
                indexes=[]
                for idx in conn.execute('PRAGMA index_list("' + name.replace('"','""') + '")'):
                    indexes.append({"name": idx["name"], "unique": bool(idx["unique"])})
                fks=[]
                for fk in conn.execute('PRAGMA foreign_key_list("' + name.replace('"','""') + '")'):
                    fks.append({"column": fk["from"], "references_table": fk["table"], "references_column": fk["to"]})
                tables.append({"name": name, "schema": "main", "type": table["type"], "columns": cols, "primary_keys": [c["name"] for c in cols if c["primary_key"]], "foreign_keys": fks, "indexes": indexes, "row_count_estimate": None})
        return success_envelope(self.driver, profile, {"database": str(self._path(profile)), "schemas": ["main"], "tables": tables, "sample_rows_included": False})

    def execute_readonly(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        row_limit = bounded_row_limit((options or {}).get("row_limit"), DEFAULT_ROW_LIMIT)
        started=time.perf_counter()
        with self._connect(profile) as conn:
            cur=conn.execute(sql)
            return query_result(self.driver, profile, cur, started, row_limit)

    def execute_user_sql(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        row_limit = bounded_row_limit((options or {}).get("row_limit"), DEFAULT_ROW_LIMIT)
        normalized = normalize_sql(sql)
        statements = normalized.statements
        if not statements:
            raise DriverError("DB_EXECUTION_FAILED", "SQL is empty.")
        classification = classify_sql(statements[0]) if len(statements) == 1 else None
        started=time.perf_counter()
        conn = self._connect(profile, read_only=False)
        try:
            conn.execute("BEGIN")
            if len(statements) == 1:
                cur=conn.execute(statements[0])
                if cur.description:
                    payload = query_result(self.driver, profile, cur, started, row_limit)
                    conn.commit()
                    return payload
                row_count = cur.rowcount
                conn.commit()
                return user_execution_result(self.driver, profile, started, row_count=row_count, statement_type=classification.statement_type if classification else "SQL")

            total_row_count = 0
            for statement in statements:
                cur = conn.execute(statement)
                if isinstance(cur.rowcount, int) and cur.rowcount > 0:
                    total_row_count += cur.rowcount
                cur.close()
            conn.commit()
            payload = user_execution_result(self.driver, profile, started, row_count=total_row_count, statement_type="BATCH")
            payload["metadata"].update({"statement_count": len(statements), "transactional_batch": True})
            return payload
        except DriverError:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise DriverError(
                "DB_EXECUTION_FAILED",
                str(exc),
                {"driver": self.driver, "statement_count": len(statements)},
            ) from exc
        finally:
            conn.close()
