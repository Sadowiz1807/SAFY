from __future__ import annotations

import pytest

from DataStore.profile_store import _normalize_database_base_url
from Gateway.db_drivers.errors import DriverError
from Gateway.db_drivers.factory import execute_readonly, get_driver
from Gateway.db_drivers.postgres_driver import PostgresDriver
from Gateway.db_drivers.provider_profiles import resolve_provider_profile
from Gateway.db_drivers.supabase_rest_driver import SupabaseRpcDriver


def test_supabase_rpc_profile_uses_rpc_driver() -> None:
    profile = {
        "provider": "supabase",
        "driver": "supabase_rpc",
        "dbms": "supabase_rpc",
        "connection_kind": "supabase_rpc",
    }
    assert isinstance(get_driver(profile), SupabaseRpcDriver)


def test_supabase_native_postgres_profile_uses_postgres_driver() -> None:
    profile = {
        "provider": "supabase",
        "driver": "postgresql",
        "dbms": "postgresql",
        "connection_kind": "native_sql",
    }
    resolved = resolve_provider_profile(profile)
    assert resolved["driver"] == "postgresql"
    assert isinstance(get_driver(profile), PostgresDriver)


def test_supabase_postgres_url_is_not_rewritten_to_rpc() -> None:
    normalized = _normalize_database_base_url(
        {
            "provider": "supabase",
            "base_url": "postgresql://db.example.supabase.co:5432/postgres",
        }
    )
    assert normalized["driver"] == "postgresql"
    assert normalized.get("connection_kind") != "supabase_rpc"


def test_supabase_https_url_is_rpc_mode() -> None:
    normalized = _normalize_database_base_url(
        {
            "provider": "supabase",
            "base_url": "https://example.supabase.co",
        }
    )
    assert normalized["driver"] == "supabase_rpc"
    assert normalized["connection_kind"] == "supabase_rpc"
    assert normalized["base_url"].endswith("/rest/v1")


def test_readonly_factory_raises_when_policy_blocks_sql() -> None:
    with pytest.raises(DriverError) as exc_info:
        execute_readonly(
            "DELETE FROM demo",
            {"provider": "self_hosted", "driver": "sqlite", "dbms": "sqlite", "database": ":memory:"},
        )
    assert exc_info.value.error_code


def test_fake_driver_user_execution_raises_instead_of_returning_failure_payload() -> None:
    from Gateway.db_drivers.factory import execute_user_sql

    with pytest.raises(DriverError) as exc_info:
        execute_user_sql(
            "CREATE TABLE demo (id INTEGER)",
            {"provider": "self_hosted", "driver": "fake", "dbms": "fake"},
        )
    assert exc_info.value.error_code == "FAKE_DB_ADAPTER_DISABLED"


def test_supabase_base_url_rejects_hostname_substring_attack() -> None:
    driver = SupabaseRpcDriver()
    with pytest.raises(DriverError) as exc_info:
        driver._base_url({"base_url": "https://project.supabase.co.attacker.example/rest/v1"})
    assert exc_info.value.error_code == "DB_BASE_URL_INVALID"


def test_supabase_base_url_accepts_project_root_and_normalizes_path() -> None:
    driver = SupabaseRpcDriver()
    assert driver._base_url({"base_url": "https://project.supabase.co"}) == "https://project.supabase.co/rest/v1"
