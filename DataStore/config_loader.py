from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import os
import tempfile

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None


class ConfigError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def to_error(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "details": self.details}


@dataclass(frozen=True)
class SafyConfig:
    app: dict[str, Any]
    policies: dict[str, Any]
    skills: dict[str, Any]
    toolsets: dict[str, Any]
    root: Path

    def data_path(self, name: str) -> Path:
        paths = self.app.get("data_paths", {})
        if name not in paths:
            raise ConfigError("CONFIG_PATH_MISSING", f"Missing data path: {name}")
        return (self.root / paths[name]).resolve()


def ensure_dir(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def load_json(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        raise ConfigError("CONFIG_FILE_MISSING", f"Required config file is missing: {target.name}")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError("CONFIG_PARSE_ERROR", f"Invalid JSON config file: {target.name}") from exc
    if not isinstance(data, dict):
        raise ConfigError("CONFIG_INVALID_SHAPE", f"Config must be an object: {target.name}")
    return data


def write_json_atomic(path: str | Path, data: dict[str, Any]) -> None:
    target = Path(path)
    ensure_dir(target.parent)
    fd, tmp = tempfile.mkstemp(prefix=target.name, suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True, ensure_ascii=True)
            handle.write("\n")
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def get_repo_root() -> Path:
    if "SAFY_HOME" in os.environ:
        return Path(os.environ["SAFY_HOME"]).resolve()
    return Path(__file__).resolve().parent.parent

class ConfigLoader:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else get_repo_root()
        self.config_dir = self.root / "Configs"

    def load(self) -> SafyConfig:
        return SafyConfig(
            app=self._load_config("app.yaml"),
            policies=self._load_config("policies.yaml"),
            skills=self._load_config("skills.yaml"),
            toolsets=self._load_config("toolsets.yaml"),
            root=self.root,
        )

    def _load_config(self, name: str) -> dict[str, Any]:
        path = self.config_dir / name
        if not path.exists():
            raise ConfigError("CONFIG_FILE_MISSING", f"Required config file is missing: {name}")
        if path.suffix.lower() == ".json":
            return load_json(path)
        if yaml is None:
            raise ConfigError("CONFIG_YAML_UNAVAILABLE", f"YAML support is unavailable: {name}")
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            raise ConfigError("CONFIG_PARSE_ERROR", f"Invalid config file: {name}") from exc
        if not isinstance(data, dict):
            raise ConfigError("CONFIG_INVALID_SHAPE", f"Config must be an object: {name}")
        return data
