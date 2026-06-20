from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import re
import uuid

from .config_loader import load_json, write_json_atomic
from Gateway.db_drivers.provider_profiles import resolve_provider_profile
from Gateway.db_drivers.errors import DriverError

ACCESS_MODES = {"credential_permissions", "read_only", "disabled"}
RAW_SECRET_KEYS = {"api_key", "password", "raw_api_key", "raw_password", "raw_secret", "secret", "token"}
SECRET_VALUE_RE = re.compile(r"^(sk-|pk_|AKIA|AIza|xox[baprs]-|ghp_)", re.I)


class ProfileStoreError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def to_error(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "details": self.details}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _looks_like_secret(value: Any) -> bool:
    return isinstance(value, str) and (SECRET_VALUE_RE.search(value) is not None or len(value) >= 32 and not value.isupper())


def _reject_raw_secrets(profile: dict[str, Any], *, allow_raw_secret: bool = False) -> None:
    """Validate secret fields.

    SAFY originally rejected all raw secrets in profiles. For the simplified
    local/dev database workflow, database profiles may intentionally store raw
    API keys/passwords when password_mode/secret_mode is set to raw_secret.
    Model profiles and *_env fields remain strict.
    """
    allowed_raw_fields = {"api_key", "password", "raw_api_key", "raw_password", "raw_secret", "secret", "token"} if allow_raw_secret else set()
    for key, value in profile.items():
        lower = key.lower()
        if lower in allowed_raw_fields:
            continue
        if lower in RAW_SECRET_KEYS or lower.endswith("_value"):
            raise ProfileStoreError("SECRET_VALUE_REJECTED", f"Raw secret field is not allowed: {key}")
        if lower in {"api_key_env", "password_env"}:
            if value in (None, ""):
                continue
            if not isinstance(value, str) or not value.replace("_", "").isalnum() or not value.upper() == value:
                raise ProfileStoreError("VALIDATION_ERROR", f"Secret environment variable name is invalid: {key}")
        elif lower in {"api_key", "password"} or (lower not in {"database", "host", "display_name", "profile_id", "base_url", "endpoint_key", "connection_kind", "execution_transport", "sql_rpc_function", "write_rpc_function", "sql_rpc_argument", "ssl_mode", "user_query_access_mode", "allowed_root"} and _looks_like_secret(value)):
            raise ProfileStoreError("SECRET_VALUE_REJECTED", "Raw secret values must not be stored in profiles.")


def _normalize_database_base_url(profile: dict[str, Any]) -> dict[str, Any]:
    """Map the simplified UI Base URL into backend database fields.

    This keeps the UI simple while preserving the older driver fields used by
    provider resolution and query/test code.
    """
    base_url = (profile.get("base_url") or "").strip()
    if not base_url:
        return profile

    parsed = urlparse(base_url)
    scheme = (parsed.scheme or "").lower()
    hostname = parsed.hostname or profile.get("host") or ""
    port = parsed.port
    path_database = (parsed.path or "").strip("/")

    provider = (profile.get("provider") or "").strip().lower()
    is_supabase = "supabase.co" in hostname or provider == "supabase"
    is_supabase_api = is_supabase and (not scheme.startswith("postgres") and not scheme.startswith("mysql") and not scheme.startswith("sqlite") and not scheme.startswith("mssql") and not scheme.startswith("sqlserver") and not scheme.startswith("oracle"))
    if provider in {"", "unified"}:
        provider = "supabase" if is_supabase else "self_hosted"
        profile["provider"] = provider
    if is_supabase_api:
        # Supabase API/RPC is a distinct database kind in SAFY. It uses baseURL
        # + API key and does not share PostgreSQL direct username/password logic.
        profile["driver"] = "supabase_rpc"
        profile["dbms"] = "supabase_rpc"
        profile["connection_kind"] = "supabase_rpc"
        profile["execution_transport"] = "postgrest_rpc"
        if base_url and "/rest/v1" not in base_url:
            profile["base_url"] = base_url.rstrip("/") + "/rest/v1"
        if hostname and not profile.get("host"):
            profile["host"] = hostname
        if not profile.get("port"):
            profile["port"] = 443
        if not profile.get("database") or str(profile.get("database")).lower() in {"rest/v1", "rest/v1/", ""}:
            profile["database"] = "supabase_api"
        if not profile.get("username"):
            profile["username"] = "supabase_api"
        if not profile.get("sql_rpc_function"):
            profile["sql_rpc_function"] = "safy_execute_sql"

    if "driver" not in profile and "dbms" not in profile:
        if scheme.startswith("mysql"):
            profile["driver"] = "mysql"
        elif scheme.startswith("sqlite"):
            profile["driver"] = "sqlite"
        else:
            profile["driver"] = "postgresql"

    driver = (profile.get("dbms") or profile.get("driver") or ("supabase_rpc" if provider == "supabase" else "postgresql")).lower()
    if driver == "postgres":
        driver = "postgresql"
    profile["driver"] = driver
    profile["dbms"] = driver

    if driver == "sqlite":
        if path_database and not profile.get("database"):
            profile["database"] = path_database
        return profile

    if hostname and not profile.get("host"):
        profile["host"] = hostname
    if port and not profile.get("port"):
        profile["port"] = port
    if not profile.get("port"):
        profile["port"] = 3306 if driver == "mysql" else 5432
    if path_database and not profile.get("database"):
        profile["database"] = path_database
    return profile


def _normalize_database_raw_secret(profile: dict[str, Any]) -> dict[str, Any]:
    env_var = (profile.get("secret_env") or profile.get("api_key_env") or profile.get("password_env") or "")
    env_var = str(env_var).strip() if env_var is not None else ""
    if env_var:
        profile["secret_env"] = env_var
        profile["api_key_env"] = env_var
        profile["password_env"] = env_var
        profile["password_mode"] = "env"
        profile["secret_mode"] = "env"
        profile["has_raw_secret"] = True
        for key in ("raw_secret", "api_key", "password", "raw_api_key", "raw_password", "secret", "token"):
            profile.pop(key, None)
        return profile

    raw = (
        profile.get("raw_secret")
        or profile.get("raw_api_key")
        or profile.get("api_key")
        or profile.get("raw_password")
        or profile.get("password")
        or ""
    )
    raw = str(raw).strip() if raw is not None else ""
    if raw:
        raise ProfileStoreError(
            "SECRET_ENV_REQUIRED",
            "Raw database secrets must be moved to .env before profile storage.",
            {"fields": ["api_key", "raw_secret", "password"]},
        )

    for key in ("raw_secret", "api_key", "password", "raw_api_key", "raw_password", "secret", "token"):
        profile.pop(key, None)
    profile.setdefault("password_mode", "none")
    profile.setdefault("secret_mode", "none")
    profile.setdefault("password_env", "")
    profile.setdefault("api_key_env", "")
    profile.setdefault("secret_env", "")
    profile.setdefault("has_raw_secret", False)
    return profile


def _require(profile: dict[str, Any], fields: list[str]) -> None:
    missing = [field for field in fields if profile.get(field) in (None, "")]
    if missing:
        raise ProfileStoreError("VALIDATION_ERROR", "Missing required profile fields.", {"fields": missing})


class JsonProfileStore:
    def __init__(self, path: str | Path, profile_type: str):
        self.path = Path(path)
        self.profile_type = profile_type
        if not self.path.exists():
            write_json_atomic(self.path, {"schema_version": 1, "profiles": []})

    def read_all(self) -> list[dict[str, Any]]:
        data = load_json(self.path)
        profiles = data.get("profiles", [])
        if not isinstance(profiles, list):
            raise ProfileStoreError("VALIDATION_ERROR", "Profile store must contain a profiles list.")
        typed = []
        for item in profiles:
            marker = item.get("profile_type")
            if marker is None:
                marker = "model" if "provider" in item or "model_name" in item else "database" if "dbms" in item else self.profile_type
            if marker == self.profile_type:
                typed.append(dict(item))
        return [self._normalize(item) for item in typed]

    def get(self, profile_id: str) -> dict[str, Any]:
        for profile in self.read_all():
            if profile["profile_id"] == profile_id:
                return profile
        raise ProfileStoreError("PROFILE_NOT_FOUND", f"Profile not found: {profile_id}")

    def save(self, profile: dict[str, Any], overwrite: bool = False) -> dict[str, Any]:
        normalized = self._normalize(dict(profile), for_write=True)
        data = load_json(self.path) if self.path.exists() else {"schema_version": 1, "profiles": []}
        profiles = [dict(item) for item in data.get("profiles", [])]
        exists = [idx for idx, item in enumerate(profiles) if item.get("profile_id") == normalized["profile_id"]]
        if exists and not overwrite:
            raise ProfileStoreError("DUPLICATE_PROFILE_ID", f"Duplicate profile_id: {normalized['profile_id']}")
        if exists:
            normalized["created_at"] = profiles[exists[0]].get("created_at") or normalized["created_at"]
            profiles[exists[0]] = normalized
        else:
            profiles.append(normalized)
        profiles.sort(key=lambda item: (item.get("profile_type", ""), item["profile_id"]))
        write_json_atomic(self.path, {"schema_version": 1, "profiles": profiles})
        return normalized

    def _normalize(self, profile: dict[str, Any], for_write: bool = False) -> dict[str, Any]:
        if self.profile_type == "database":
            profile = _normalize_database_raw_secret(profile)
            _reject_raw_secrets(profile, allow_raw_secret=False)
        else:
            _reject_raw_secrets(profile, allow_raw_secret=False)
        stamp = now_iso()
        profile.setdefault("profile_id", f"{self.profile_type}_{uuid.uuid4().hex[:12]}")
        profile.setdefault("profile_type", self.profile_type)
        profile.setdefault("display_name", profile["profile_id"])
        profile.setdefault("created_at", stamp)
        profile["updated_at"] = stamp if for_write else profile.get("updated_at", stamp)
        if self.profile_type == "database":
            profile = _normalize_database_base_url(profile)
            profile = _normalize_database_raw_secret(profile)
            if "access_mode" in profile and "user_query_access_mode" not in profile:
                profile["user_query_access_mode"] = profile.pop("access_mode")
            profile.pop("access_mode", None)
            if "driver" in profile and "dbms" not in profile:
                profile["dbms"] = profile["driver"]
            if "dbms" in profile and "driver" not in profile:
                profile["driver"] = profile["dbms"]
            try:
                profile = resolve_provider_profile(profile)
            except DriverError as exc:
                raise ProfileStoreError(exc.error_code, str(exc), exc.details) from exc
            profile.setdefault("real_db_readonly", False)

            if str(profile.get("dbms", "")).lower() == "sqlite":
                profile.setdefault("host", "local_file")
                profile.setdefault("port", 0)
                profile.setdefault("username", "")
                profile.setdefault("password_env", "")
                _require(profile, ["profile_id", "display_name", "dbms", "database", "user_query_access_mode", "created_at", "updated_at"])
            else:
                required = ["profile_id", "display_name", "dbms", "host", "port", "database", "username", "user_query_access_mode", "created_at", "updated_at"]
                if profile.get("password_mode") == "env":
                    required.append("password_env")
                elif profile.get("password_mode") == "raw_secret":
                    if not profile.get("raw_secret"):
                        raise ProfileStoreError("VALIDATION_ERROR", "Missing raw_secret for password_mode=raw_secret.")
                    profile["password_env"] = ""
                _require(profile, required)
            if profile["user_query_access_mode"] not in ACCESS_MODES:
                raise ProfileStoreError("VALIDATION_ERROR", "Invalid user_query_access_mode.", {"allowed": sorted(ACCESS_MODES)})
        elif self.profile_type == "model":
            if "model" in profile and "model_name" not in profile:
                profile["model_name"] = profile.pop("model")
            _require(profile, ["profile_id", "display_name", "provider", "base_url", "api_key_env", "model_name", "created_at", "updated_at"])
        else:
            _require(profile, ["profile_id", "display_name", "created_at", "updated_at"])
        return profile


def model_profile_store(path: str | Path) -> JsonProfileStore:
    return JsonProfileStore(path, "model")


def database_profile_store(path: str | Path) -> JsonProfileStore:
    return JsonProfileStore(path, "database")


def user_store(path: str | Path) -> JsonProfileStore:
    return JsonProfileStore(path, "user")
