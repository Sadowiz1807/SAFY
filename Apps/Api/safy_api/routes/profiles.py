from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import os
import re

from fastapi import APIRouter

from Apps.Api.safy_api.runtime_store import envelope, error_envelope
from DataStore.env_writer import EnvWriter, EnvWriterError
from DataStore.profile_store import ProfileStoreError, database_profile_store
from Gateway.db_drivers.errors import DriverError
from Gateway.db_drivers.factory import test_connection
from LLM.provider_health import test_profile as test_model_profile
from LLM.provider_profiles import ModelProfileError
from LLM.provider_store import ModelProviderStore

router = APIRouter()

MASKED_VALUES = {"", "********", "[REDACTED]", "***ENV_REF***", "<REDACTED>"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _env_path() -> Path:
    return _repo_root() / ".env"


def _model_store() -> ModelProviderStore:
    return ModelProviderStore(_repo_root() / "Data" / "model_profiles" / "model_profiles.json")


def _database_store():
    return database_profile_store(_repo_root() / "Data" / "safy_profiles.json")


def _active_database(store=None) -> dict[str, Any] | None:
    store = store or _database_store()
    for profile in store.read_all():
        if profile.get("active") or profile.get("is_active"):
            return profile
    profiles = store.read_all()
    return profiles[0] if profiles else None


def _default_database_profile() -> dict[str, Any]:
    return {
        "profile_id": "db_default",
        "display_name": "Official Runtime DB",
        "driver": "postgresql",
        "database": "safy_official",
        "active": True,
        "is_active": True,
        "mode": "real",
        "real_db_readonly": True,
        "connection_status": "ok",
    }


def _safe_error(exc: Exception, fallback_code: str = "PROFILE_ERROR"):
    code = getattr(exc, "code", None) or getattr(exc, "error_code", None) or fallback_code
    details = getattr(exc, "details", {}) or {}
    return error_envelope(str(code), str(exc), details)


def _resolve_model_value(*sources: dict[str, Any] | None) -> str:
    """Return the first non-empty model alias from request/store objects."""
    for source in sources:
        if not source:
            continue
        value = (
            source.get("model")
            or source.get("model_id")
            or source.get("model_name")
            or source.get("deployment")
        )
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _public_model(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    """Public model profile serializer.

    Storage/runtime keep the real env reference. API/UI only receive redacted
    env references and model/model_id compatibility aliases.
    """
    if not profile:
        return None
    public = dict(profile)
    for key in ("api_key", "raw_api_key", "secret", "token", "password"):
        public.pop(key, None)
    model = _resolve_model_value(public)
    if model:
        public["model"] = model
        public["model_id"] = model
    for key in ("api_key_env", "secret_env", "password_env"):
        if public.get(key):
            public[key] = "***ENV_REF***"
    public["is_active"] = bool(public.get("is_active") or public.get("active"))
    return public


def _write_secret_if_new(env_name: str | None, value: Any) -> bool:
    if not env_name or value in (None, "") or str(value) in MASKED_VALUES:
        return False
    EnvWriter(_env_path()).write_secret(str(env_name), str(value), overwrite_confirmed=True)
    os.environ[str(env_name)] = str(value)
    return True


def _public_database(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    if not profile:
        return None
    public = dict(profile)
    for key in ("api_key", "password", "raw_secret", "raw_api_key", "raw_password", "secret", "token"):
        public.pop(key, None)
    for key in ("api_key_env", "password_env", "secret_env"):
        if public.get(key):
            public[key] = "***ENV_REF***"
    public["is_active"] = bool(public.get("active") or public.get("is_active"))
    return public


def _normalize_model_payload(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    profile_id = payload.get("profile_id") or payload.get("id") or (existing or {}).get("profile_id")
    model = _resolve_model_value(payload, existing)
    env_name = payload.get("api_key_env_name") or payload.get("api_key_env") or (existing or {}).get("api_key_env") or "OPENROUTER_API_KEY"
    api_key = payload.get("api_key") or payload.get("raw_api_key")
    _write_secret_if_new(env_name, api_key)
    normalized = {
        **(existing or {}),
        "profile_id": profile_id,
        "display_name": payload.get("display_name") or payload.get("name") or payload.get("profile_name") or profile_id,
        "provider_type": payload.get("provider_type") or payload.get("provider") or (existing or {}).get("provider_type") or "openrouter",
        "base_url": payload.get("base_url") or (existing or {}).get("base_url") or "",
        "model": model,
        "model_id": model,
        "api_key_env": env_name,
        "auth_mode": payload.get("auth_mode") or (existing or {}).get("auth_mode") or "env_api_key",
        "is_active": bool(payload.get("is_active", payload.get("active", (existing or {}).get("is_active", False)))),
        "context_window": payload.get("context_length") or payload.get("context_window") or (existing or {}).get("context_window"),
        "capabilities": (existing or {}).get("capabilities") or {"chat": True, "tool_calling": "optional_or_detected", "json_mode": "optional_or_detected"},
    }
    return normalized


def _normalize_database_payload(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    data = {**(existing or {})}
    profile_id = payload.get("profile_id") or payload.get("id") or data.get("profile_id")
    driver = (payload.get("driver") or payload.get("database_type") or payload.get("dbms") or data.get("driver") or "postgresql")
    mode = payload.get("mode") or payload.get("connection_kind") or data.get("mode")
    display_name = payload.get("display_name") or payload.get("name") or payload.get("profile_name") or profile_id
    transient_fields = {"api_key", "password", "raw_secret", "raw_password", "api_key_env_name", "password_env_name", "project_url", "rest_url", "rpc_function_name", "direct_postgres"}
    data.update({k: v for k, v in payload.items() if k not in transient_fields})
    data["profile_id"] = profile_id
    data["display_name"] = display_name
    data["driver"] = driver
    data["dbms"] = driver
    data["database_type"] = driver
    data["user_query_access_mode"] = payload.get("user_query_access_mode") or payload.get("access_mode") or data.get("user_query_access_mode") or "credential_permissions"
    data["active"] = bool(payload.get("is_active", payload.get("active", data.get("active", False))))

    if str(driver).lower() == "supabase":
        project_url = (payload.get("project_url") or payload.get("base_url") or payload.get("rest_url") or data.get("base_url") or "").rstrip("/")
        rest_url = (payload.get("rest_url") or project_url).rstrip("/")
        if not rest_url.endswith("/rest/v1"):
            rest_url = rest_url + "/rest/v1"
        env_name = payload.get("api_key_env_name") or payload.get("api_key_env") or data.get("secret_env") or "SUPABASE_SERVICE_ROLE_KEY"
        _write_secret_if_new(env_name, payload.get("api_key") or payload.get("raw_secret"))
        data.update({
            "driver": "supabase_rpc",
            "dbms": "supabase_rpc",
            "database_type": "supabase_rpc",
            "base_url": rest_url,
            "provider": "supabase",
            "connection_kind": "supabase_rpc" if mode != "rest_readonly" else "supabase_rest",
            "execution_transport": "postgrest_rpc" if mode != "rest_readonly" else "postgrest_readonly",
            "secret_env": env_name,
            "api_key_env": env_name,
            "password_mode": "env",
            "secret_mode": "env",
            "sql_rpc_function": payload.get("rpc_function_name") or payload.get("sql_rpc_function") or "safy_execute_sql",
            "sql_rpc_argument": payload.get("sql_rpc_argument") or "sql",
        })
    elif str(driver).lower() == "sqlite":
        sqlite_path = payload.get("sqlite_path") or payload.get("database") or data.get("sqlite_path") or data.get("database") or ""
        data.update({
            "driver": "sqlite",
            "dbms": "sqlite",
            "database_type": "sqlite",
            "provider": payload.get("provider") or data.get("provider") or "self_hosted",
            "connection_kind": "native_sql",
            "execution_transport": "native_driver",
            "sqlite_path": sqlite_path,
            "database": sqlite_path,
            "host": "local_file",
            "port": 0,
            "username": "",
            "authentication": "none",
            "password_mode": "none",
            "secret_mode": "none",
            "password_env": "",
            "secret_env": "",
            "api_key_env": "",
        })
    elif str(driver).lower() in {"sqlserver", "sql_server", "mssql"}:
        auth_mode = str(payload.get("auth_mode") or payload.get("authentication") or data.get("authentication") or "sql").lower()
        windows = auth_mode in {"windows", "trusted", "trusted_connection"}
        env_name = payload.get("password_env_name") or payload.get("password_env") or data.get("password_env") or "SQLSERVER_PASSWORD"
        if not windows:
            _write_secret_if_new(env_name, payload.get("password") or payload.get("raw_password"))
        data.update({
            "driver": "sqlserver",
            "dbms": "sqlserver",
            "database_type": "sqlserver",
            "host": payload.get("host") or data.get("host") or "",
            "port": payload.get("port") or data.get("port") or 1433,
            "instance": payload.get("instance") or data.get("instance") or "",
            "database": payload.get("database") or data.get("database") or "",
            "authentication": "windows" if windows else "sql_server",
            "trusted_connection": windows,
            "username": "" if windows else (payload.get("username") or payload.get("user") or data.get("username") or ""),
            "password_mode": "none" if windows else "env",
            "secret_mode": "none" if windows else "env",
            "password_env": "" if windows else env_name,
            "encrypt": payload.get("encrypt", data.get("encrypt", "optional")),
            "trust_server_certificate": bool(payload.get("trust_server_certificate", payload.get("trust_cert", data.get("trust_server_certificate", True)))),
            "timeout_seconds": int(payload.get("timeout_seconds") or data.get("timeout_seconds") or 10),
        })
    else:
        parsed = urlparse(str(payload.get("base_url") or data.get("base_url") or ""))
        db_from_url = (parsed.path or "").strip("/") if parsed else ""
        secret = payload.get("password") or payload.get("raw_secret") or (parsed.password if parsed else None)
        env_default = re.sub(r"[^A-Z0-9]+", "_", str(profile_id or "DATABASE").upper()).strip("_") or "DATABASE"
        env_name = payload.get("password_env_name") or payload.get("password_env") or data.get("password_env") or f"{env_default}_PASSWORD"
        wrote_secret = _write_secret_if_new(env_name, secret)
        data.update({
            "provider": payload.get("provider") or data.get("provider") or "self_hosted",
            "connection_kind": "native_sql",
            "execution_transport": "native_driver",
            "host": payload.get("host") or data.get("host") or (parsed.hostname if parsed else None) or "localhost",
            "port": payload.get("port") or data.get("port") or (parsed.port if parsed else None),
            "database": payload.get("database") or data.get("database") or db_from_url,
            "username": payload.get("username") or payload.get("user") or data.get("username") or (parsed.username if parsed else None) or "",
            "authentication": payload.get("authentication") or data.get("authentication") or "password",
            "password_mode": "env" if wrote_secret or payload.get("preserve_secret") or data.get("password_env") else "none",
            "secret_mode": "env" if wrote_secret or payload.get("preserve_secret") or data.get("secret_env") else "none",
            "password_env": env_name if wrote_secret or payload.get("preserve_secret") or data.get("password_env") else "",
            "secret_env": env_name if wrote_secret or payload.get("preserve_secret") or data.get("secret_env") else "",
            "ssl_mode": payload.get("ssl_mode") or data.get("ssl_mode") or "preferred",
            "timeout_seconds": int(payload.get("timeout_seconds") or data.get("timeout_seconds") or 15),
        })
        if not data.get("port"):
            data["port"] = {"postgresql": 5432, "postgres": 5432, "mysql": 3306, "oracle": 1521}.get(str(driver).lower(), 5432)
    return data


@router.get("/model-profiles")
def list_model_profiles() -> dict[str, Any]:
    return envelope([_public_model(profile) for profile in _model_store().list(redacted=False)])


@router.get("/model-profiles/active")
def active_model_profile() -> dict[str, Any]:
    try:
        return envelope(_public_model(_model_store().active(redacted=False)))
    except ModelProfileError as exc:
        return _safe_error(exc, "MODEL_PROFILE_NOT_FOUND")


@router.post("/model-profiles")
def save_model_profile(payload: dict[str, Any]) -> dict[str, Any]:
    store = _model_store()
    existing = None
    profile_id = payload.get("profile_id") or payload.get("id")
    if profile_id:
        try:
            existing = store.get(str(profile_id), redacted=False)
        except ModelProfileError:
            existing = None
    try:
        normalized = _normalize_model_payload(payload, existing)
        if not _resolve_model_value(normalized):
            return error_envelope("LLM_MODEL_MISSING", "Model profile requires a non-empty model.", {"profile_id": profile_id})
        saved = store.save(normalized, overwrite=existing is not None)
        if payload.get("is_active") or payload.get("active"):
            saved = store.activate(saved["profile_id"])
        return envelope({"profile": _public_model(saved), "profile_id": saved["profile_id"], "saved": True, "code": "MODEL_PROFILE_SAVED"})
    except (ModelProfileError, EnvWriterError) as exc:
        return _safe_error(exc, "MODEL_PROFILE_SAVE_FAILED")


@router.post("/model-profiles/{profile_id}/activate")
def activate_model_profile(profile_id: str) -> dict[str, Any]:
    try:
        profile = _model_store().activate(profile_id)
        return envelope({"profile": _public_model(profile), "profile_id": profile_id, "activated": True, "code": "MODEL_PROFILE_ACTIVATED"})
    except ModelProfileError as exc:
        return _safe_error(exc, "MODEL_PROFILE_ACTIVATE_FAILED")


@router.post("/model-profiles/{profile_id}/test")
def test_model_profile_route(profile_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    try:
        stored_profile = _model_store().get(profile_id, redacted=False)
        profile = _normalize_model_payload(payload, stored_profile) if payload else dict(stored_profile)
        model = _resolve_model_value(profile, stored_profile)
        if not model:
            return error_envelope("LLM_MODEL_MISSING", "Model profile test requires a non-empty model.", {"profile_id": profile_id})
        profile["model"] = model
        profile["model_id"] = model

        env_name = profile.get("api_key_env")
        if profile.get("auth_mode") == "env_api_key" and env_name and not os.environ.get(str(env_name)) and _env_path().exists():
            # EnvWriter persists to .env for local runtime. Load a single value for this test
            # without exposing the secret through the public serializer.
            for line in _env_path().read_text(encoding="utf-8").splitlines():
                if line.startswith(f"{env_name}="):
                    os.environ[str(env_name)] = line.split("=", 1)[1].strip()
                    break

        result = test_model_profile(profile)
        if result.get("success"):
            return envelope({"ok": True, "code": "MODEL_PROFILE_TEST_PASSED", "result": result, "profile": _public_model(profile)})
        status = str(result.get("status") or result.get("code") or "LLM_TEST_FAILED")
        code = (
            "LLM_API_KEY_ENV_MISSING" if "ENV" in status and "MISSING" in status else
            "LLM_API_KEY_MISSING" if "API_KEY_MISSING" in status else
            "LLM_AUTH_FAILED" if "AUTH_FAILED" in status else
            "LLM_MODEL_NOT_FOUND" if "MODEL_NOT_FOUND" in status else
            "LLM_PROVIDER_TIMEOUT" if "TIMEOUT" in status else
            "LLM_PROVIDER_UNREACHABLE" if "UNREACHABLE" in status else
            "LLM_TEST_FAILED"
        )
        return error_envelope(code, "Model profile test failed.", {"provider_status": status, "profile_id": profile_id, "profile": _public_model(profile), "result": result})
    except ModelProfileError as exc:
        return _safe_error(exc, "MODEL_PROFILE_TEST_FAILED")
    except Exception as exc:
        return _safe_error(exc, "MODEL_PROFILE_TEST_FAILED")


@router.get("/database-profiles")
def list_database_profiles() -> dict[str, Any]:
    profiles = [_public_database(p) for p in _database_store().read_all()]
    return envelope(profiles or [_default_database_profile()])


@router.get("/database-profiles/active")
def active_database_profile() -> dict[str, Any]:
    profile = _active_database()
    if not profile:
        return envelope(_default_database_profile())
    return envelope(_public_database(profile))


@router.post("/database-profiles")
def save_database_profile(payload: dict[str, Any]) -> dict[str, Any]:
    store = _database_store()
    existing = None
    profile_id = payload.get("profile_id") or payload.get("id")
    if profile_id:
        try:
            existing = store.get(str(profile_id))
        except ProfileStoreError:
            existing = None
    try:
        saved = store.save(_normalize_database_payload(payload, existing), overwrite=existing is not None)
        if payload.get("is_active") or payload.get("active"):
            saved = store.activate(saved["profile_id"])
        return envelope({"profile": _public_database(saved), "profile_id": saved["profile_id"], "saved": True, "code": "DATABASE_PROFILE_SAVED"})
    except (ProfileStoreError, EnvWriterError, DriverError, ValueError) as exc:
        return _safe_error(exc, "DATABASE_PROFILE_SAVE_FAILED")


@router.post("/database-profiles/{profile_id}/activate")
def activate_database_profile(profile_id: str) -> dict[str, Any]:
    try:
        profile = _database_store().activate(profile_id)
        return envelope({"profile": _public_database(profile), "profile_id": profile_id, "activated": True, "code": "DATABASE_PROFILE_ACTIVATED"})
    except ProfileStoreError as exc:
        return _safe_error(exc, "DATABASE_PROFILE_ACTIVATE_FAILED")


def _secret_context(profile: dict[str, Any]) -> dict[str, Any]:
    env_name = profile.get("secret_env") or profile.get("api_key_env") or profile.get("password_env") or ""
    secret = os.environ.get(env_name) if env_name else None
    if not secret and env_name and _env_path().exists():
        for line in _env_path().read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{env_name}="):
                secret = line.split("=", 1)[1].strip()
                break
    return {"password": secret} if secret else {}


@router.post("/database-profiles/test")
def test_database_profile_route(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        profile = _normalize_database_payload(payload, None)
        driver = str(profile.get("driver") or profile.get("database_type") or "").lower()
        if driver == "sqlserver":
            required = ["host", "database", "authentication"]
            missing = [key for key in required if not profile.get(key) or str(profile.get(key)).startswith("TODO_USER_FILL")]
            if profile.get("authentication") not in {"windows", "sql_server"}:
                missing.append("auth_mode")
            if missing:
                return error_envelope("LIVE_SQLSERVER_TEST_BLOCKED_MISSING_FIELD", "SQL Server live test requires completed connection fields.", {"missing_fields": sorted(set(missing)), "profile_preview": _public_database(profile)})
        mode = str(payload.get("mode") or profile.get("connection_kind") or "").lower()
        if driver in {"supabase", "supabase_rpc"} and mode == "rest_readonly":
            parsed = urlparse(profile.get("base_url") or "")
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                return error_envelope("SUPABASE_URL_INVALID", "Supabase URL is invalid.")
            return envelope({"ok": True, "code": "SUPABASE_REST_CONNECTIVITY_OK", "message": "REST connectivity shape is valid; DDL/DML execution unsupported in rest_readonly mode.", "profile_preview": _public_database(profile)})
        result = test_connection(profile, _secret_context(profile))
        if result.get("success"):
            return envelope({"ok": True, "code": "DATABASE_TEST_PASSED", "result": result, "profile_preview": _public_database(profile)})
        return error_envelope("DATABASE_TEST_FAILED", "Database connection test failed.", result)
    except DriverError as exc:
        code = exc.error_code
        if "SUPABASE" in code and "RPC" in code:
            code = "SUPABASE_RPC_NOT_INSTALLED" if "NOT" in code or "404" in str(exc.details) else code
        if "pyodbc" in str(exc).lower() or "odbc" in str(exc).lower():
            code = "MSSQL_DRIVER_MISSING"
        return error_envelope(code, str(exc), exc.details)
    except (ProfileStoreError, EnvWriterError, ValueError) as exc:
        return _safe_error(exc, "DATABASE_TEST_FAILED")
