from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from .security import validate_pack_archive

class DomainPackReader:
    def __init__(self, pack_path: str | Path):
        self.pack_path = Path(pack_path)
        validation = validate_pack_archive(self.pack_path)
        if not validation["valid"]:
            raise ValueError(f"invalid domain pack: {validation['errors']}")
        self._zip = zipfile.ZipFile(self.pack_path)
        self.manifest = self.read_json("manifest.json")

    def close(self) -> None:
        self._zip.close()

    def read_text(self, name: str) -> str:
        return self._zip.read(name).decode("utf-8")

    def read_json(self, name: str) -> Any:
        return json.loads(self.read_text(name))

    def read_jsonl(self, name: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for line in self.read_text(name).splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
