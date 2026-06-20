from __future__ import annotations

from pathlib import Path
import json
from .sandbox_state import now_iso

FORBIDDEN_KEYS = {"password", "dsn", "rows", "result", "backup_contents"}

class SandboxAudit:
    def __init__(self, sandbox_dir: Path):
        self.path = sandbox_dir / "audit.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, action: str, sandbox_id: str, status: str = "success", **metadata) -> dict:
        clean = {k: v for k, v in metadata.items() if k not in FORBIDDEN_KEYS}
        event = {"timestamp": now_iso(), "action": action, "sandbox_id": sandbox_id, "status": status, **clean}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True) + "\n")
        return event

    def read(self, limit: int = 100) -> list[dict]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
        return [json.loads(line) for line in lines if line.strip()]
