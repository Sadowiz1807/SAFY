from __future__ import annotations
from typing import Any
from .base import SecretContext, driver_name
from .errors import DriverError
from Gateway.real_db_policy import real_db_policy
from .sqlite_driver import SQLiteDriver
from .mysql_driver import MySQLDriver
from .postgres_driver import PostgresDriver
from .provider_profiles import resolve_provider_profile
from .sqlserver_driver import SQLServerDriver
from .oracle_driver import OracleDriver
from .supabase_rest_driver import SupabaseRpcDriver

def get_driver(profile: dict[str, Any]):
    connection_kind = str(profile.get("connection_kind") or "").lower()
    requested_driver = str(profile.get("driver") or profile.get("dbms") or "").lower()
    if connection_kind in {"supabase_rpc", "supabase_rest"} or requested_driver in {"supabase_rpc", "supabase_rest"}:
        return SupabaseRpcDriver()
    profile = resolve_provider_profile(profile)
    name = driver_name(profile)
    if name == "sqlite": return SQLiteDriver()
    if name == "mysql": return MySQLDriver()
    if name in {"postgres", "postgresql"}: return PostgresDriver()
    if name == "sqlserver": return SQLServerDriver()
    if name == "oracle": return OracleDriver()
    if name == "fake": return None
    raise DriverError("DBMS_UNSUPPORTED", f"Unsupported database driver: {name}")

def _secret(secret_context: dict[str, Any] | SecretContext | None) -> SecretContext | None:
    if secret_context is None or isinstance(secret_context, SecretContext): return secret_context
    return SecretContext(password=secret_context.get("password"))

def test_connection(profile: dict[str, Any], secret_context: dict[str, Any] | SecretContext | None = None) -> dict[str, Any]:
    profile = resolve_provider_profile(profile)
    driver = get_driver(profile)
    if driver is None:
        return {"success": True, "driver": "fake", "database_profile_id": profile.get("profile_id") or "main_database", "metadata": {"runtime_preview_only": True}, "warnings": []}
    return driver.test_connection(profile, _secret(secret_context))

def get_schema(profile: dict[str, Any], secret_context: dict[str, Any] | SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = resolve_provider_profile(profile)
    driver = get_driver(profile)
    if driver is None:
        return {"success": True, "driver": "fake", "database_profile_id": profile.get("profile_id") or "main_database", "metadata": {"database": "fake", "tables": []}, "warnings": []}
    return driver.get_schema(profile, _secret(secret_context), options)

def execute_readonly(sql: str, profile: dict[str, Any], secret_context: dict[str, Any] | SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = resolve_provider_profile(profile)
    policy = real_db_policy(sql)
    if not policy.get("allowed"):
        raise DriverError(
            policy.get("error_code") or "DB_UNSAFE_SQL_BLOCKED",
            "SQL blocked by SAFY read-only guard before driver execution.",
            {"statement_type": policy.get("statement_type")},
        )
    driver = get_driver(profile)
    if driver is None:
        return {"success": True, "driver": "fake", "database_profile_id": profile.get("profile_id") or "main_database", "columns": ["id"], "rows": [{"id": 1}], "row_count": 1, "metadata": {"temporary_rows": True, "no_result_persistence": True, "read_only": True}, "warnings": []}
    return driver.execute_readonly(sql, profile, _secret(secret_context), options)

def execute_user_sql(sql: str, profile: dict[str, Any], secret_context: dict[str, Any] | SecretContext | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = resolve_provider_profile(profile)
    driver = get_driver(profile)
    if driver is None:
        raise DriverError(
            "FAKE_DB_ADAPTER_DISABLED",
            "Fake DB adapter cannot execute real user SQL.",
        )
    if not hasattr(driver, "execute_user_sql"):
        raise DriverError("DB_USER_EXECUTION_UNSUPPORTED", f"{driver_name(profile)} driver does not support user-controlled write execution.")
    return driver.execute_user_sql(sql, profile, _secret(secret_context), options)
