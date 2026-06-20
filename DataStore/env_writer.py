from __future__ import annotations

from pathlib import Path
import os
import tempfile


class EnvWriterError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class EnvWriter:
    def __init__(self, env_path: str | Path):
        self.env_path = Path(env_path)

    def read(self) -> dict[str, str]:
        if not self.env_path.exists():
            return {}
        values: dict[str, str] = {}
        for line in self.env_path.read_text(encoding="utf-8").splitlines():
            if not line or line.strip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value
        return values

    def write_secret(self, key: str, value: str, overwrite_confirmed: bool = False) -> dict[str, object]:
        if not key or not key.replace("_", "").isalnum() or key.upper() != key:
            raise EnvWriterError("VALIDATION_ERROR", "Environment variable name is invalid.")
        if value in (None, ""):
            raise EnvWriterError("VALIDATION_ERROR", "Secret value is required.")
        if "\n" in value or "\r" in value:
            raise EnvWriterError("VALIDATION_ERROR", "Secret value must be a single line.")
        current = self.read()
        if key in current and not overwrite_confirmed:
            raise EnvWriterError("PROFILE_OVERWRITE_CONFIRMATION_REQUIRED", "Environment variable already exists.")
        current[key] = value
        self._atomic_write(current)
        return {"env_var": key, "secret_configured": True, "secret_mask": "[REDACTED]"}

    def _atomic_write(self, values: dict[str, str]) -> None:
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".env", suffix=".tmp", dir=str(self.env_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                for key in sorted(values):
                    handle.write(f"{key}={values[key]}\n")
            os.replace(tmp, self.env_path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
