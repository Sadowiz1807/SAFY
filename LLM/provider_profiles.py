from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
import re
import uuid

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
SECRET_FIELDS = {"api_key", "raw_api_key", "token", "secret", "password"}
ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
PROVIDER_ALIASES = {
    "lm_studio": "lmstudio",
    "lm-studio": "lmstudio",
    "lm studio": "lmstudio",
    "openai_compat": "openai_compatible",
    "openai-compatible": "openai_compatible",
    "openai compatible": "openai_compatible",
}


class ModelProfileError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(message)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def is_local_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() in LOCAL_HOSTS


def redact_profile(profile: dict[str, Any]) -> dict[str, Any]:
    public = dict(profile)
    if public.get("api_key_env"):
        public["api_key_env"] = "***ENV_REF***"
    public.pop("api_key", None)
    public.pop("raw_api_key", None)
    return public


@dataclass
class ModelProviderProfile:
    profile_id: str
    display_name: str
    provider_type: str
    base_url: str
    model: str
    api_key_env: str | None = None
    auth_mode: str = "env_api_key"
    is_active: bool = False
    capabilities: dict[str, Any] = field(default_factory=dict)
    context_window: int | None = None
    request_timeout_seconds: int = 180
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    @classmethod
    def from_dict(cls, data: dict[str, Any], for_write: bool = False) -> "ModelProviderProfile":
        for key in data:
            if key.lower() in SECRET_FIELDS or key.lower().endswith("_value"):
                raise ModelProfileError("SECRET_VALUE_REJECTED", f"Raw secret field is not allowed: {key}")
        model = data.get("model") or data.get("model_name")
        profile = cls(
            profile_id=data.get("profile_id") or f"model_{uuid.uuid4().hex[:12]}",
            display_name=data.get("display_name") or data.get("profile_id") or "Model provider",
            provider_type=PROVIDER_ALIASES.get((data.get("provider_type") or data.get("provider") or "openai_compatible").strip().lower(), (data.get("provider_type") or data.get("provider") or "openai_compatible").strip().lower()),
            base_url=(data.get("base_url") or "").rstrip("/"),
            model=model or "",
            api_key_env=data.get("api_key_env"),
            auth_mode=data.get("auth_mode") or ("local_no_auth" if data.get("local_no_auth") else "env_api_key"),
            is_active=bool(data.get("is_active", data.get("active", False))),
            capabilities=dict(data.get("capabilities") or {"chat": True, "tool_calling": "optional_or_detected", "json_mode": "optional_or_detected"}),
            context_window=data.get("context_window"),
            request_timeout_seconds=180,
            created_at=data.get("created_at") or now_iso(),
            updated_at=now_iso() if for_write else data.get("updated_at") or now_iso(),
        )
        profile.validate()
        return profile

    def validate(self) -> None:
        if not self.base_url or not self.model:
            raise ModelProfileError("VALIDATION_ERROR", "base_url and model are required.")
        allowed = {"openai_compatible", "openai_compat", "lmstudio", "ollama", "ollama_openai", "openai", "openrouter", "custom_router"}
        if self.provider_type not in allowed:
            raise ModelProfileError("VALIDATION_ERROR", "Unsupported provider_type.", {"provider_type": self.provider_type})
        if self.auth_mode == "local_no_auth":
            if not is_local_base_url(self.base_url):
                raise ModelProfileError("REMOTE_NO_AUTH_BLOCKED", "local_no_auth is allowed only for localhost/private local providers.")
            self.api_key_env = None
        elif self.auth_mode == "env_api_key":
            if not self.api_key_env or not ENV_RE.match(self.api_key_env):
                raise ModelProfileError("VALIDATION_ERROR", "api_key_env must be an uppercase environment variable reference.")
        else:
            raise ModelProfileError("VALIDATION_ERROR", "Unsupported auth_mode.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "display_name": self.display_name,
            "provider_type": self.provider_type,
            "base_url": self.base_url,
            "model": self.model,
            "api_key_env": self.api_key_env,
            "auth_mode": self.auth_mode,
            "is_active": self.is_active,
            "capabilities": self.capabilities,
            "context_window": self.context_window,
            "request_timeout_seconds": self.request_timeout_seconds,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
