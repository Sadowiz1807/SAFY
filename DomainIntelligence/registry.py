from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DomainRegistry:
    """Portable registry for compiled SAFY domain packs."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.domain_root = self.root / "DomainIntelligence"
        self.path = self.domain_root / "packs" / "registry.json"

    def _storage_path(self) -> Path | None:
        if self.path.exists():
            return self.path
        return None

    def _resolve_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        row = dict(entry)
        value = row.get("path")
        if value:
            pack_path = Path(str(value))
            if not pack_path.is_absolute():
                pack_path = (self.root / pack_path).resolve()
            row["path"] = str(pack_path)
        return row

    def _portable_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        row = dict(entry)
        value = row.get("path")
        if value:
            pack_path = Path(str(value))
            if pack_path.is_absolute():
                try:
                    row["path"] = pack_path.resolve().relative_to(self.root).as_posix()
                except ValueError:
                    row["path"] = str(pack_path)
            else:
                row["path"] = pack_path.as_posix()
        return row

    def load(self) -> dict[str, Any]:
        storage = self._storage_path()
        if storage is None:
            return {
                "format": "safy-domain-registry",
                "format_version": "1.0.0",
                "domains": [],
            }
        data = json.loads(storage.read_text(encoding="utf-8"))
        data["domains"] = [
            self._resolve_entry(row) for row in data.get("domains") or []
        ]
        return data

    def packs(self) -> list[dict[str, Any]]:
        return list(self.load().get("domains") or [])

    def enabled_packs(self) -> list[dict[str, Any]]:
        return [p for p in self.packs() if p.get("enabled", True)]

    def get(self, domain_id: str) -> dict[str, Any] | None:
        for pack in self.enabled_packs():
            if pack.get("domain_id") == domain_id:
                return pack
        return None

    def write(self, registry: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(registry)
        payload["domains"] = [
            self._portable_entry(row) for row in registry.get("domains") or []
        ]
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)
