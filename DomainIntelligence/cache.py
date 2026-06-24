from __future__ import annotations

import json
from pathlib import Path
from typing import Any

class DomainCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.path = self.root / "DomainIntelligence" / "packs" / "cache" / "schema_domain_cache.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def get(self, database_profile_id: str | None, schema_fingerprint: str, pack_version: str | None) -> dict[str, Any] | None:
        for row in self._read():
            if row.get("database_profile_id") == database_profile_id and row.get("schema_fingerprint") == schema_fingerprint and row.get("domain_pack_version") == pack_version:
                return row
        return None

    def put(self, row: dict[str, Any]) -> None:
        rows = [r for r in self._read() if not (r.get("database_profile_id") == row.get("database_profile_id") and r.get("schema_fingerprint") == row.get("schema_fingerprint"))]
        rows.append(row)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
