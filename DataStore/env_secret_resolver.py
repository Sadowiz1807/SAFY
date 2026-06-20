from __future__ import annotations

from pathlib import Path
from typing import Any
import os


class SecretResolverError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def to_error(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "details": self.details}


class EnvSecretResolver:
    def __init__(self, env_path: str | Path | None = None):
        self.env_path = Path(env_path) if env_path else None
        self._file_values = self._read_file()

    def resolve(self, env_var: str) -> str:
        if not env_var or not env_var.replace("_", "").isalnum():
            raise SecretResolverError("VALIDATION_ERROR", "Environment variable name is invalid.")
        value = os.environ.get(env_var) or self._file_values.get(env_var)
        if value in (None, ""):
            raise SecretResolverError("SECRET_ENV_MISSING", f"Missing environment secret: {env_var}")
        return value

    def safe_status(self, env_var: str) -> dict[str, object]:
        try:
            self.resolve(env_var)
            return {"env_var": env_var, "secret_configured": True, "secret_mask": "[REDACTED]"}
        except SecretResolverError as exc:
            return {"env_var": env_var, "secret_configured": False, "secret_mask": None, "error_code": exc.code}

    def _read_file(self) -> dict[str, str]:
        if not self.env_path or not self.env_path.exists():
            return {}
        values: dict[str, str] = {}
        for line in self.env_path.read_text(encoding="utf-8").splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value
        return values
