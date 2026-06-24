from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .sandbox_state import now_iso

FORBIDDEN_KEYS = {
    "password",
    "dsn",
    "rows",
    "result",
    "backup_contents",
    "sql",
    "raw_sql",
    "normalized_sql",
    "redacted_sql",
    "executed_sql",
    "query_text",
}


def _sanitize_metadata(value: Any) -> Any:
    """Remove secrets, result rows, and SQL text before sandbox audit persistence."""
    if isinstance(value, dict):
        return {
            key: _sanitize_metadata(item)
            for key, item in value.items()
            if str(key).lower() not in FORBIDDEN_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_metadata(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_metadata(item) for item in value]
    return value


class SandboxAudit:
    def __init__(self, sandbox_dir: Path):
        self.path = sandbox_dir / "audit.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, action: str, sandbox_id: str, status: str = "success", **metadata) -> dict:
        clean = _sanitize_metadata(metadata)
        event = {"timestamp": now_iso(), "action": action, "sandbox_id": sandbox_id, "status": status, **clean}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True) + "\n")
        return event

    def read(self, limit: int = 100) -> list[dict]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
        return [json.loads(line) for line in lines if line.strip()]
