from __future__ import annotations

from pathlib import Path
import os

from DataStore.config_loader import ConfigLoader, SafyConfig


_CONFIG_CACHE: SafyConfig | None = None


def repo_root() -> Path:
    explicit = os.environ.get("SAFY_HOME")
    if explicit:
        return Path(explicit).resolve()
    return Path(__file__).resolve().parents[3]


def load_config() -> SafyConfig:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        _CONFIG_CACHE = ConfigLoader(repo_root()).load()
    return _CONFIG_CACHE
