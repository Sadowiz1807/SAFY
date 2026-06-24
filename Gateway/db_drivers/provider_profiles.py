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
    "aurora_mysql": "mysql",
    "aurora-mysql": "mysql",
    "sqlite": "sqlite",
    "sqlserver": "sqlserver",
    "sql_server": "sqlserver",
    "mssql": "sqlserver",
    "oracle": "oracle",
}

_ALLOWED = {
    "self_hosted": {"sqlite", "mysql", "postgresql", "sqlserver", "oracle", "fake"},
    SUPABASE: {"supabase_rpc", "postgresql"},
    GOOGLE_CLOUD_SQL: {"mysql", "postgresql", "sqlserver"},
    AWS_AURORA: {"mysql", "postgresql"},
}

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


def resolve_provider_profile(profile: dict[str, Any]) -> dict[str, Any]:
    provider = normalize_provider(profile.get("provider"))
    requested = profile.get("engine") or profile.get("driver") or profile.get("dbms")
    driver = normalize_driver(requested, provider)
    allowed = _ALLOWED.get(provider)
    if allowed is None:
        raise DriverError("PROVIDER_UNSUPPORTED", f"Unsupported database provider: {provider}")
    if driver not in allowed:
        raise DriverError("PROVIDER_DRIVER_UNSUPPORTED", f"Provider {provider} does not support driver {driver}.", {"provider": provider, "driver": driver, "allowed_drivers": sorted(allowed)})
    resolved = dict(profile)
    resolved["provider"] = provider
    resolved["driver"] = driver
    resolved["dbms"] = driver
    resolved.setdefault("read_only", True)
    resolved.setdefault("real_db_readonly", True)
    return resolved


def provider_driver_matrix() -> dict[str, list[str]]:
    return {provider: sorted(drivers) for provider, drivers in _ALLOWED.items()}
