from __future__ import annotations

from pathlib import Path
import json
import sqlite3
from .sandbox_state import now_iso

class SchemaCache:
    def __init__(self, sandbox_dir: Path):
        self.path = sandbox_dir / "schema_cache.json"

    def write_empty(self, dbms: str) -> dict:
        data = {"generated_at": now_iso(), "dbms": dbms, "tables": []}
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        return data

    def generate_sqlite(self, db_path: Path) -> dict:
        tables = []
        with sqlite3.connect(db_path) as conn:
            for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
                cols = [{"name": r[1], "type": r[2]} for r in conn.execute(f"PRAGMA table_info({name})")]
                tables.append({"name": name, "columns": cols})
        data = {"generated_at": now_iso(), "dbms": "sqlite", "tables": tables}
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        return data

    def write_postgres(self, tables: list[dict]) -> dict:
        data = {"generated_at": now_iso(), "dbms": "postgresql", "tables": tables}
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        return data

    def read(self) -> dict:
        if not self.path.exists():
            return {"tables": [], "schema_cache_available": False}
        return json.loads(self.path.read_text(encoding="utf-8"))
