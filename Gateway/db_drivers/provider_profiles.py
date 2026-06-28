from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import DriverError

SELF_HOSTED = "self_hosted"
SUPABASE = "supabase"
GOOGLE_CLOUD_SQL = "google_cloud_sql"
AWS_AURORA = "aws_aurora"

_PROVIDER_ALIASES = {
    "": SELF_HOSTED,
    "direct": SELF_HOSTED,
    "self-hosted": SELF_HOSTED,
    "self_hosted": SELF_HOSTED,
    "supabase": SUPABASE,
    "cloud_sql": GOOGLE_CLOUD_SQL,
    "google_cloud_sql": GOOGLE_CLOUD_SQL,
    "google cloud sql": GOOGLE_CLOUD_SQL,
    "aurora": AWS_AURORA,
    "amazon_aurora": AWS_AURORA,
    "aws_aurora": AWS_AURORA,
}

ENGINE_ALIASES = {
    "supabase": "supabase_rpc",
    "supabase_rest": "supabase_rpc",
    "supabase_api": "supabase_rpc",
    "supabase-rpc": "supabase_rpc",
    "supabase_rpc": "supabase_rpc",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "aurora_postgresql": "postgresql",
    "aurora-postgresql": "postgresql",
    "mysql": "mysql",
    "mariadb": "mysql",
    "aurora_mysql": "mysql",
    "aurora-mysql": "mysql",
    "sqlite": "sqlite",
    "sqlserver": "sqlserver",
    "sql_server": "sqlserver",
    "mssql": "sqlserver",
    "oracle": "oracle",
}

_CONNECTION_KIND_ALIASES = {
    "": "native",
    "native_sql": "native",
    "native": "native",
    "postgresql": "native",
    "file": "file",
    "local_file": "file",
    "rest": "rest",
    "postgrest": "rest",
    "supabase_rest": "rest",
    "rpc": "rpc",
    "postgrest_rpc": "rpc",
    "supabase_rpc": "rpc",
}

_DBMS_BY_DRIVER = {
    "supabase_rpc": "postgresql",
    "supabase_rest": "postgresql",
    "postgresql": "postgresql",
    "mysql": "mysql",
    "sqlite": "sqlite",
    "sqlserver": "sqlserver",
    "oracle": "oracle",
    "fake": "fake",
}

_DIALECT_BY_DBMS = {
    "postgresql": "postgresql",
    "mysql": "mysql",
    "sqlite": "sqlite",
    "sqlserver": "sqlserver",
    "oracle": "oracle",
    "fake": "sqlite",
}

_SANDBOX_ADAPTER_BY_DBMS = {
    "postgresql": "postgresql",
    "mysql": "mysql",
    "sqlite": "sqlite",
    "sqlserver": "sqlserver",
    "oracle": "oracle",
    "fake": "sqlite",
}

_ALLOWED = {
    "self_hosted": {"sqlite", "mysql", "postgresql", "sqlserver", "oracle", "fake"},
    SUPABASE: {"supabase_rpc", "postgresql"},
    GOOGLE_CLOUD_SQL: {"mysql", "postgresql", "sqlserver"},
    AWS_AURORA: {"mysql", "postgresql"},
}

@dataclass(frozen=True)
class DatabaseCapability:
    provider: str
    connection_kind: str
    transport: str
    driver: str
    dbms: str
    dialect: str
    sandbox_adapter: str
    supports_read: bool
    supports_complex_read: bool
    supports_write: bool
    supports_ddl: bool
    supports_schema_graph: bool
    supports_sandbox: bool
    live_certification: str = "not_certified"


@dataclass(frozen=True)
class ProviderResolution:
    provider: str
    requested_driver: str
    driver: str


def normalize_provider(provider: Any) -> str:
    key = str(provider or SELF_HOSTED).strip().lower()
    return _PROVIDER_ALIASES.get(key, key)


def normalize_driver(driver: Any, provider: Any = None) -> str:
    raw = str(driver or "").strip().lower()
    if not raw and normalize_provider(provider) == SUPABASE:
        raw = "supabase_rpc"
    return ENGINE_ALIASES.get(raw, raw)


def _normalize_connection_kind(profile: dict[str, Any], driver: str) -> str:
    raw = str(profile.get("connection_kind") or profile.get("execution_transport") or "").strip().lower()
    if driver == "supabase_rpc" and raw in {"", "native", "native_sql"}:
        return "rpc"
    if driver == "sqlite" and raw in {"", "native", "native_sql"}:
        return "file"
    return _CONNECTION_KIND_ALIASES.get(raw, raw or "native")


def resolve_database_capability(profile: dict[str, Any]) -> DatabaseCapability:
    provider = normalize_provider(profile.get("provider"))
    requested = profile.get("database_type") or profile.get("engine") or profile.get("driver") or profile.get("dbms")
    driver = normalize_driver(requested, provider)
    allowed = _ALLOWED.get(provider)
    if allowed is None:
        raise DriverError("PROVIDER_UNSUPPORTED", f"Unsupported database provider: {provider}")
    if driver not in allowed:
        raise DriverError("PROVIDER_DRIVER_UNSUPPORTED", f"Provider {provider} does not support driver {driver}.", {"provider": provider, "driver": driver, "allowed_drivers": sorted(allowed)})
    connection_kind = _normalize_connection_kind(profile, driver)
    transport = "rpc" if driver == "supabase_rpc" else connection_kind
    dbms = _DBMS_BY_DRIVER.get(driver, driver)
    dialect = _DIALECT_BY_DBMS.get(dbms, dbms)
    sandbox_adapter = _SANDBOX_ADAPTER_BY_DBMS.get(dbms, dbms)
    supports_native_sql = driver not in {"supabase_rpc", "supabase_rest"}
    supports_read = True
    supports_complex_read = supports_native_sql or bool(profile.get("read_rpc_function"))
    supports_write = bool(supports_native_sql or profile.get("write_rpc_function") or profile.get("sql_rpc_function"))
    supports_ddl = bool(supports_native_sql or profile.get("write_rpc_function") or profile.get("sql_rpc_function"))
    supports_schema_graph = dbms in {"postgresql", "mysql", "sqlite", "sqlserver", "oracle"}
    supports_sandbox = sandbox_adapter in {"postgresql", "mysql", "sqlite", "sqlserver", "oracle"}
    return DatabaseCapability(
        provider=provider,
        connection_kind=connection_kind,
        transport=transport,
        driver=driver,
        dbms=dbms,
        dialect=dialect,
        sandbox_adapter=sandbox_adapter,
        supports_read=supports_read,
        supports_complex_read=supports_complex_read,
        supports_write=supports_write,
        supports_ddl=supports_ddl,
        supports_schema_graph=supports_schema_graph,
        supports_sandbox=supports_sandbox,
    )


def resolve_provider_profile(profile: dict[str, Any]) -> dict[str, Any]:
    requested = profile.get("engine") or profile.get("driver") or profile.get("dbms")
    capability = resolve_database_capability({**profile, "database_type": profile.get("database_type") or requested})
    resolved = dict(profile)
    resolved["provider"] = capability.provider
    resolved["connection_kind"] = capability.connection_kind
    resolved["transport"] = capability.transport
    resolved["driver"] = capability.driver
    resolved["dbms"] = capability.dbms
    resolved["dialect"] = capability.dialect
    resolved["sandbox_adapter"] = capability.sandbox_adapter
    resolved["supports_read"] = capability.supports_read
    resolved["supports_complex_read"] = capability.supports_complex_read
    resolved["supports_write"] = capability.supports_write
    resolved["supports_ddl"] = capability.supports_ddl
    resolved["supports_schema_graph"] = capability.supports_schema_graph
    resolved["supports_sandbox"] = capability.supports_sandbox
    resolved["live_certification"] = capability.live_certification
    resolved.setdefault("read_only", True)
    resolved.setdefault("real_db_readonly", True)
    return resolved


def provider_driver_matrix() -> dict[str, list[str]]:
    return {provider: sorted(drivers) for provider, drivers in _ALLOWED.items()}
