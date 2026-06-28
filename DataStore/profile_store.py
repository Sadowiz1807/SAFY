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
        elif lower in {"api_key", "password"} or (lower not in {"database", "sqlite_path", "host", "display_name", "profile_id", "base_url", "endpoint_key", "connection_kind", "execution_transport", "sql_rpc_function", "write_rpc_function", "sql_rpc_argument", "ssl_mode", "user_query_access_mode", "allowed_root"} and _looks_like_secret(value)):
            raise ProfileStoreError("SECRET_VALUE_REJECTED", "Raw secret values must not be stored in profiles.")


DATABASE_TYPE_ALIASES = {
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "aurora_postgresql": "postgresql",
    "supabase": "supabase_rpc",
    "supabase_api": "supabase_rpc",
    "supabase_rest": "supabase_rpc",
    "supabase_rpc": "supabase_rpc",
    "mysql": "mysql",
    "mariadb": "mysql",
    "aurora_mysql": "mysql",
    "sqlite": "sqlite",
    "sql_server": "sqlserver",
    "sqlserver": "sqlserver",
    "mssql": "sqlserver",
    "oracle": "oracle",
}

DATABASE_DEFAULT_PORTS = {
    "postgresql": 5432,
    "supabase_rpc": 443,
    "mysql": 3306,
    "sqlite": 0,
    "sqlserver": 1433,
    "oracle": 1521,
}


def _nonempty(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _infer_database_type(profile: dict[str, Any]) -> str:
    requested = _nonempty(
        profile.get("database_type")
        or profile.get("driver")
        or profile.get("dbms")
        or profile.get("engine")
    ).lower()
    if requested:
        canonical = DATABASE_TYPE_ALIASES.get(requested, requested)
        if canonical in DATABASE_DEFAULT_PORTS:
            return canonical

    base_url = _nonempty(profile.get("base_url"))
    lowered = base_url.lower()
    if "supabase.co" in lowered and not lowered.startswith(("postgres://", "postgresql://")):
        return "supabase_rpc"
    if lowered.startswith(("postgres://", "postgresql://")):
        return "postgresql"
    if lowered.startswith(("mysql://", "mariadb://")):
        return "mysql"
    if lowered.startswith("sqlite://") or lowered.endswith((".sqlite", ".db")):
        return "sqlite"
    if lowered.startswith(("sqlserver://", "mssql://")):
        return "sqlserver"
    if lowered.startswith("oracle://"):
        return "oracle"
    return "postgresql"


def normalize_database_connection_payload(profile: dict[str, Any]) -> dict[str, Any]:
    """Classify and normalize the unified database-profile JSON contract.

    Structured fields are authoritative. ``base_url`` is parsed only to fill
    missing fields and to keep older clients compatible.
    """
    normalized = dict(profile)
    database_type = _infer_database_type(normalized)
    normalized["database_type"] = database_type
    normalized["driver"] = database_type
    normalized["dbms"] = database_type
    normalized["engine"] = database_type

    provider = _nonempty(normalized.get("provider")).lower()
    if provider in {"", "unified", "direct"}:
        provider = "supabase" if database_type == "supabase_rpc" else "self_hosted"
    normalized["provider"] = provider

    base_url = _nonempty(normalized.get("base_url"))
    parsed = None
    if base_url and database_type != "sqlite":
        try:
            parsed = urlparse(base_url)
        except Exception:
            parsed = None

    if database_type == "supabase_rpc":
        normalized["provider"] = "supabase"
        normalized["connection_kind"] = "supabase_rpc"
        normalized["execution_transport"] = "postgrest_rpc"
        normalized["authentication"] = "api_key"
        normalized["secret_kind"] = "api_key"
        if base_url:
            normalized_url = base_url if "://" in base_url else f"https://{base_url}"
            parsed = urlparse(normalized_url)
            host = parsed.hostname or ""
            normalized["host"] = _nonempty(normalized.get("host")) or host
            path = (parsed.path or "").rstrip("/")
            if path.lower().endswith("/rest/v1"):
                normalized["base_url"] = normalized_url.rstrip("/")
            else:
                normalized["base_url"] = normalized_url.rstrip("/") + "/rest/v1"
        normalized["port"] = int(normalized.get("port") or 443)
        normalized["database"] = "supabase_api"
        normalized["username"] = "supabase_api"
        normalized["ssl_mode"] = "api"
        normalized["sql_rpc_function"] = _nonempty(normalized.get("sql_rpc_function")) or "safy_execute_sql"
        normalized["sql_rpc_argument"] = _nonempty(normalized.get("sql_rpc_argument")) or "sql"
        return normalized

    normalized.setdefault("connection_kind", "native_sql")
    normalized.setdefault("execution_transport", "native_driver")

    if database_type == "sqlite":
        sqlite_path = _nonempty(normalized.get("sqlite_path") or normalized.get("database") or base_url)
        if sqlite_path.lower().startswith("sqlite://"):
            sqlite_path = sqlite_path[9:]
        normalized["sqlite_path"] = sqlite_path
        normalized["database"] = sqlite_path
        normalized["base_url"] = f"sqlite://{sqlite_path}" if sqlite_path else ""
        normalized["host"] = "local_file"
        normalized["port"] = 0
        normalized["username"] = ""
        normalized["authentication"] = "none"
        normalized["secret_kind"] = "none"
        normalized["trusted_connection"] = False
        return normalized

    # URL-derived values only fill missing structured fields.
    if parsed and parsed.hostname:
        normalized["host"] = _nonempty(normalized.get("host")) or parsed.hostname
        if normalized.get("port") in (None, "", 0) and parsed.port:
            normalized["port"] = parsed.port
        if not _nonempty(normalized.get("database")):
            normalized["database"] = (parsed.path or "").strip("/")

    normalized["host"] = _nonempty(normalized.get("host")) or "localhost"
    raw_port = normalized.get("port")
    if database_type == "sqlserver" and _nonempty(normalized.get("instance")) and raw_port in (None, "", 0, "0"):
        normalized["port"] = 0
    else:
        normalized["port"] = int(raw_port or DATABASE_DEFAULT_PORTS[database_type])

    if database_type == "sqlserver":
        auth = _nonempty(normalized.get("authentication")).lower()
        if auth in {"windows", "trusted", "trusted_connection", "integrated", "integrated_security"} or bool(normalized.get("trusted_connection")):
            auth = "windows"
            normalized["trusted_connection"] = True
            normalized["username"] = ""
            normalized["secret_kind"] = "none"
        else:
            auth = "sql_server"
            normalized["trusted_connection"] = False
            normalized["secret_kind"] = "password"
        normalized["authentication"] = auth
        normalized["instance"] = _nonempty(normalized.get("instance"))
        normalized["encrypt"] = bool(normalized.get("encrypt", True))
        normalized["trust_server_certificate"] = bool(normalized.get("trust_server_certificate", False))
        normalized["odbc_driver"] = _nonempty(normalized.get("odbc_driver")) or "ODBC Driver 18 for SQL Server"
    elif database_type == "oracle":
        service_name = _nonempty(normalized.get("service_name"))
        sid = _nonempty(normalized.get("sid"))
        database = _nonempty(normalized.get("database"))
        if not service_name and not sid:
            service_name = database
        normalized["service_name"] = service_name
        normalized["sid"] = sid
        normalized["database"] = database or service_name or sid
        normalized["authentication"] = "password"
        normalized["secret_kind"] = "password"
    else:
        normalized["authentication"] = "password"
        normalized["secret_kind"] = "password"
        normalized["ssl_mode"] = _nonempty(normalized.get("ssl_mode")) or "preferred"

    if not base_url:
        scheme = {"postgresql": "postgresql", "mysql": "mysql", "sqlserver": "sqlserver", "oracle": "oracle"}[database_type]
        database = _nonempty(normalized.get("database") or normalized.get("service_name") or normalized.get("sid"))
        normalized["base_url"] = f"{scheme}://{normalized['host']}:{normalized['port']}/{database}"
    return normalized


def _normalize_database_base_url(profile: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible alias for unified connection classification."""
    return normalize_database_connection_payload(profile)

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

    def activate(self, profile_id: str) -> dict[str, Any]:
        if self.profile_type != "database":
            raise ProfileStoreError("UNSUPPORTED_OPERATION", "activate() is only supported for database profiles in this store.")
        data = load_json(self.path) if self.path.exists() else {"schema_version": 1, "profiles": []}
        profiles = [dict(item) for item in data.get("profiles", [])]
        target_index = next((idx for idx, item in enumerate(profiles) if item.get("profile_id") == profile_id and (item.get("profile_type") in {None, "database"})), None)
        if target_index is None:
            raise ProfileStoreError("PROFILE_NOT_FOUND", f"Profile not found: {profile_id}")
        stamp = now_iso()
        activated: dict[str, Any] | None = None
        next_profiles: list[dict[str, Any]] = []
        for item in profiles:
            next_item = dict(item)
            if next_item.get("profile_type") in {None, "database"}:
                is_target = next_item.get("profile_id") == profile_id
                next_item["active"] = is_target
                next_item["activation_generation"] = int(next_item.get("activation_generation") or 0) + (1 if is_target else 0)
                next_item["context_generation"] = int(next_item.get("context_generation") or 0) + (1 if is_target else 0)
                next_item["updated_at"] = stamp
                if is_target:
                    activated = self._normalize(next_item, for_write=False)
            next_profiles.append(next_item)
        write_json_atomic(self.path, {"schema_version": data.get("schema_version", 1), "profiles": next_profiles})
        return activated or self.get(profile_id)

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
            database_type = str(profile.get("database_type") or profile.get("dbms") or "").lower()

            if database_type == "sqlite":
                profile.setdefault("host", "local_file")
                profile.setdefault("port", 0)
                profile.setdefault("username", "")
                profile.setdefault("password_env", "")
                _require(profile, ["profile_id", "display_name", "dbms", "database", "user_query_access_mode", "created_at", "updated_at"])
            elif database_type == "supabase_rpc":
                _require(profile, ["profile_id", "display_name", "dbms", "base_url", "host", "port", "database", "user_query_access_mode", "created_at", "updated_at"])
                if profile.get("password_mode") == "env" or profile.get("secret_mode") == "env":
                    _require(profile, ["secret_env"])
            elif database_type == "sqlserver" and profile.get("authentication") == "windows":
                _require(profile, ["profile_id", "display_name", "dbms", "host", "database", "user_query_access_mode", "created_at", "updated_at"])
                profile["username"] = ""
                profile["password_mode"] = "none"
                profile["secret_mode"] = "none"
                profile["password_env"] = ""
                profile["api_key_env"] = ""
                profile["secret_env"] = ""
                profile["has_raw_secret"] = False
            else:
                required = ["profile_id", "display_name", "dbms", "host", "port", "database", "username", "user_query_access_mode", "created_at", "updated_at"]
                if database_type == "oracle" and not (profile.get("service_name") or profile.get("sid") or profile.get("database")):
                    raise ProfileStoreError("VALIDATION_ERROR", "Oracle service_name or sid is required.")
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
