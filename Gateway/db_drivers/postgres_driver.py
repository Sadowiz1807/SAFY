from __future__ import annotations
from typing import Any
import time
from .base import bounded_row_limit, DEFAULT_ROW_LIMIT, SecretContext, query_result, resolve_secret, success_envelope, is_sensitive_name, user_execution_result
from .errors import DriverError
from Gateway.sql_classifier import classify_sql
from Gateway.sql_normalizer import normalize_sql

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
        conn = self._connect(profile, secret_context)
        try:
            relation_rows = conn.execute(
                """
                SELECT ns.nspname AS table_schema,
                       cls.relname AS table_name,
                       CASE cls.relkind
                         WHEN 'r' THEN 'table'
                         WHEN 'p' THEN 'partition'
                         WHEN 'v' THEN 'view'
                         WHEN 'm' THEN 'materialized_view'
                         WHEN 'f' THEN 'table'
                         ELSE 'table'
                       END AS table_type
                  FROM pg_catalog.pg_class cls
                  JOIN pg_catalog.pg_namespace ns ON ns.oid = cls.relnamespace
                 WHERE cls.relkind IN ('r', 'p', 'v', 'm', 'f')
                   AND ns.nspname NOT IN ('pg_catalog', 'information_schema')
                   AND ns.nspname NOT LIKE 'pg_toast%'
                 ORDER BY ns.nspname, cls.relname
                """
            ).fetchall()

            foreign_key_rows = conn.execute(
                """
                SELECT con.conname AS constraint_name,
                       src_ns.nspname AS source_schema,
                       src.relname AS source_table,
                       src_att.attname AS source_column,
                       tgt_ns.nspname AS target_schema,
                       tgt.relname AS target_table,
                       tgt_att.attname AS target_column,
                       pairs.ordinality AS ordinal_position,
                       con.confupdtype AS update_action,
                       con.confdeltype AS delete_action
                  FROM pg_catalog.pg_constraint con
                  JOIN pg_catalog.pg_class src ON src.oid = con.conrelid
                  JOIN pg_catalog.pg_namespace src_ns ON src_ns.oid = src.relnamespace
                  JOIN pg_catalog.pg_class tgt ON tgt.oid = con.confrelid
                  JOIN pg_catalog.pg_namespace tgt_ns ON tgt_ns.oid = tgt.relnamespace
                  CROSS JOIN LATERAL unnest(con.conkey, con.confkey)
                       WITH ORDINALITY AS pairs(source_attnum, target_attnum, ordinality)
                  JOIN pg_catalog.pg_attribute src_att
                    ON src_att.attrelid = src.oid AND src_att.attnum = pairs.source_attnum
                  JOIN pg_catalog.pg_attribute tgt_att
                    ON tgt_att.attrelid = tgt.oid AND tgt_att.attnum = pairs.target_attnum
                 WHERE con.contype = 'f'
                 ORDER BY src_ns.nspname, src.relname, con.conname, pairs.ordinality
                """
            ).fetchall()

            action_names = {
                "a": "NO ACTION",
                "r": "RESTRICT",
                "c": "CASCADE",
                "n": "SET NULL",
                "d": "SET DEFAULT",
            }
            foreign_keys_by_table: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
            for row in foreign_key_rows:
                table_key = (row["source_schema"], row["source_table"])
                constraints = foreign_keys_by_table.setdefault(table_key, {})
                constraint = constraints.setdefault(row["constraint_name"], {
                    "constraint_name": row["constraint_name"],
                    "columns": [],
                    "references_schema": row["target_schema"],
                    "references_table": row["target_table"],
                    "references_columns": [],
                    "on_update": action_names.get(row["update_action"], "NO ACTION"),
                    "on_delete": action_names.get(row["delete_action"], "NO ACTION"),
                    "cardinality": "many_to_one",
                })
                constraint["columns"].append(row["source_column"])
                constraint["references_columns"].append(row["target_column"])

            inheritance_rows = conn.execute(
                """
                SELECT child_ns.nspname AS child_schema,
                       child.relname AS child_table,
                       parent_ns.nspname AS parent_schema,
                       parent.relname AS parent_table,
                       child.relispartition AS is_partition
                  FROM pg_catalog.pg_inherits inheritance
                  JOIN pg_catalog.pg_class child ON child.oid = inheritance.inhrelid
                  JOIN pg_catalog.pg_namespace child_ns ON child_ns.oid = child.relnamespace
                  JOIN pg_catalog.pg_class parent ON parent.oid = inheritance.inhparent
                  JOIN pg_catalog.pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
                 WHERE child_ns.nspname NOT IN ('pg_catalog', 'information_schema')
                 ORDER BY child_ns.nspname, child.relname, parent_ns.nspname, parent.relname
                """
            ).fetchall()
            relationships = [
                {
                    "relationship_type": "partition_parent" if row["is_partition"] else "inheritance",
                    "source_schema": row["child_schema"],
                    "source_node_id": f"{row['child_schema']}.{row['child_table']}",
                    "target_schema": row["parent_schema"],
                    "target_node_id": f"{row['parent_schema']}.{row['parent_table']}",
                    "evidence": "postgres_catalog",
                    "confidence": 1.0,
                }
                for row in inheritance_rows
            ]

            tables = []
            for relation in relation_rows:
                schema = relation["table_schema"]
                name = relation["table_name"]
                columns = [
                    {
                        "name": column["column_name"],
                        "data_type": column["data_type"],
                        "nullable": bool(column["nullable"]),
                        "primary_key": False,
                        "unique": False,
                        "default": column["column_default"],
                        "generated": column["generated"],
                        "ordinal_position": column["ordinal_position"],
                        "sensitive": is_sensitive_name(column["column_name"]),
                    }
                    for column in conn.execute(
                        """
                        SELECT attr.attname AS column_name,
                               pg_catalog.format_type(attr.atttypid, attr.atttypmod) AS data_type,
                               NOT attr.attnotnull AS nullable,
                               pg_catalog.pg_get_expr(def.adbin, def.adrelid) AS column_default,
                               attr.attnum AS ordinal_position,
                               NULLIF(attr.attgenerated, '') AS generated
                          FROM pg_catalog.pg_attribute attr
                          JOIN pg_catalog.pg_class cls ON cls.oid = attr.attrelid
                          JOIN pg_catalog.pg_namespace ns ON ns.oid = cls.relnamespace
                          LEFT JOIN pg_catalog.pg_attrdef def
                            ON def.adrelid = attr.attrelid AND def.adnum = attr.attnum
                         WHERE ns.nspname = %s
                           AND cls.relname = %s
                           AND attr.attnum > 0
                           AND NOT attr.attisdropped
                         ORDER BY attr.attnum
                        """,
                        (schema, name),
                    ).fetchall()
                ]

                constraint_rows = conn.execute(
                    """
                    SELECT con.conname AS constraint_name,
                           con.contype AS constraint_type,
                           attr.attname AS column_name,
                           keys.ordinality AS ordinal_position
                      FROM pg_catalog.pg_constraint con
                      JOIN pg_catalog.pg_class cls ON cls.oid = con.conrelid
                      JOIN pg_catalog.pg_namespace ns ON ns.oid = cls.relnamespace
                      CROSS JOIN LATERAL unnest(con.conkey)
                           WITH ORDINALITY AS keys(attnum, ordinality)
                      JOIN pg_catalog.pg_attribute attr
                        ON attr.attrelid = cls.oid AND attr.attnum = keys.attnum
                     WHERE ns.nspname = %s
                       AND cls.relname = %s
                       AND con.contype IN ('p', 'u')
                     ORDER BY con.contype, con.conname, keys.ordinality
                    """,
                    (schema, name),
                ).fetchall()
                primary_keys = [row["column_name"] for row in constraint_rows if row["constraint_type"] == "p"]
                primary_key_name = next((row["constraint_name"] for row in constraint_rows if row["constraint_type"] == "p"), None)
                unique_map: dict[str, list[str]] = {}
                for row in constraint_rows:
                    if row["constraint_type"] == "u":
                        unique_map.setdefault(row["constraint_name"], []).append(row["column_name"])
                unique_constraints = [{"name": key, "columns": value} for key, value in unique_map.items()]
                unique_columns = {column for value in unique_map.values() for column in value}
                for column in columns:
                    column["primary_key"] = column["name"] in primary_keys
                    column["unique"] = column["name"] in unique_columns

                index_rows = conn.execute(
                    """
                    SELECT index_cls.relname AS index_name,
                           idx.indisunique AS is_unique,
                           access_method.amname AS method,
                           pg_catalog.pg_get_indexdef(idx.indexrelid) AS definition
                      FROM pg_catalog.pg_index idx
                      JOIN pg_catalog.pg_class table_cls ON table_cls.oid = idx.indrelid
                      JOIN pg_catalog.pg_namespace ns ON ns.oid = table_cls.relnamespace
                      JOIN pg_catalog.pg_class index_cls ON index_cls.oid = idx.indexrelid
                      JOIN pg_catalog.pg_am access_method ON access_method.oid = index_cls.relam
                     WHERE ns.nspname = %s AND table_cls.relname = %s
                     ORDER BY index_cls.relname
                    """,
                    (schema, name),
                ).fetchall()
                indexes = [
                    {
                        "name": row["index_name"],
                        "unique": bool(row["is_unique"]),
                        "method": row["method"],
                        "definition": row["definition"],
                        "columns": [],
                    }
                    for row in index_rows
                ]
                tables.append({
                    "schema": schema,
                    "name": name,
                    "type": relation["table_type"],
                    "columns": columns,
                    "primary_key_name": primary_key_name,
                    "primary_keys": primary_keys,
                    "unique_constraints": unique_constraints,
                    "foreign_keys": list(foreign_keys_by_table.get((schema, name), {}).values()),
                    "indexes": indexes,
                    "row_count_estimate": None,
                })

            return success_envelope(
                self.driver,
                profile,
                {
                    "database": profile.get("database"),
                    "schemas": sorted({table["schema"] for table in tables}),
                    "tables": tables,
                    "relationships": relationships,
                    "sample_rows_included": False,
                    "relationship_metadata": "postgres_catalog",
                },
                tables=tables,
                relationships=relationships,
            )
        finally:
            conn.close()
    def execute_readonly(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        row_limit=bounded_row_limit((options or {}).get("row_limit"), DEFAULT_ROW_LIMIT); conn=self._connect(profile, secret_context); started=time.perf_counter()
        try:
            cur=conn.execute(sql)
            return query_result(self.driver, profile, cur, started, row_limit)
        finally: conn.close()

    def execute_user_sql(self, sql: str, profile: dict[str, Any], secret_context: SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        row_limit=bounded_row_limit((options or {}).get("row_limit"), DEFAULT_ROW_LIMIT)
        normalized = normalize_sql(sql)
        statements = normalized.statements
        if not statements:
            raise DriverError("DB_EXECUTION_FAILED", "SQL is empty.")
        classification = classify_sql(statements[0]) if len(statements) == 1 else None
        conn=self._connect(profile, secret_context, read_only=False)
        started=time.perf_counter()
        try:
            conn.autocommit=False
            if len(statements) == 1:
                cur=conn.execute(statements[0])
                if cur.description:
                    payload = query_result(self.driver, profile, cur, started, row_limit)
                    conn.commit()
                    return payload
                row_count = getattr(cur, "rowcount", 0)
                conn.commit()
                return user_execution_result(self.driver, profile, started, row_count=row_count, statement_type=classification.statement_type if classification else "SQL")

            total_row_count = 0
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
                    row_count = getattr(cur, "rowcount", 0)
                    if isinstance(row_count, int) and row_count > 0:
                        total_row_count += row_count
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
