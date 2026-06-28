from __future__ import annotations

from pathlib import Path
import json
import re
from .sandbox_state import SandboxRecord

SAFE_ID = re.compile(r"[^a-zA-Z0-9_-]+")

def safe_id(value: str) -> str:
    raw = value.strip()
    cleaned = SAFE_ID.sub("_", raw)[:80]
    if cleaned != raw or not cleaned:
        raise ValueError("SANDBOX_INVALID_ID")
    return cleaned

class SandboxStore:
    def __init__(self, data_root: Path):
        self.root = data_root / "sandboxes"
        self.root.mkdir(parents=True, exist_ok=True)

    def sandbox_dir(self, sandbox_id: str) -> Path:
        return self.root / safe_id(sandbox_id)

    def metadata_path(self, sandbox_id: str) -> Path:
        return self.sandbox_dir(sandbox_id) / "metadata.json"

    def save(self, record: SandboxRecord) -> dict:
        d = self.sandbox_dir(record.sandbox_id)
        d.mkdir(parents=True, exist_ok=True)
        payload = record.to_dict()
        text = json.dumps(payload, indent=2, sort_keys=True)
        lower = text.lower()
        if "password" in lower and "readonly_credential_ref" not in lower:
            raise ValueError("RAW_SECRET_IN_METADATA")
        self.metadata_path(record.sandbox_id).write_text(text, encoding="utf-8")
        return payload

    def get(self, sandbox_id: str) -> SandboxRecord:
        path = self.metadata_path(sandbox_id)
        if not path.exists():
            raise KeyError("SANDBOX_NOT_FOUND")
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("schema_cache_available", None)
        if "readonly_secret_ref" in data and "readonly_credential_ref" not in data:
            data["readonly_credential_ref"] = data.pop("readonly_secret_ref")
        return SandboxRecord(**data)

    def list(self) -> list[SandboxRecord]:
        records = []
        for path in sorted(self.root.glob("*/metadata.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            data.pop("schema_cache_available", None)
            if "readonly_secret_ref" in data and "readonly_credential_ref" not in data:
                data["readonly_credential_ref"] = data.pop("readonly_secret_ref")
            records.append(SandboxRecord(**data))
        return records

    def active_for_scope(self, project_id: str, workspace_id: str) -> SandboxRecord | None:
        for record in self.list():
            if record.active and record.project_id == project_id and record.workspace_id == workspace_id and record.state != "deleted":
                return record
        return None

    def delete_files(self, sandbox_id: str) -> None:
        path = self.sandbox_dir(sandbox_id)
        if not path.exists():
            return
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        path.rmdir()
