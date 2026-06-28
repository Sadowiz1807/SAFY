from __future__ import annotations

from pathlib import Path
import sqlite3


class SQLiteSandboxRunner:
    def execute(self, db_path: Path, statement: str) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.execute(statement)

    def read_schema(self, db_path: Path) -> dict:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute("SELECT type, name, sql FROM sqlite_master WHERE type IN ('table','view','index') AND name NOT LIKE 'sqlite_%' ORDER BY type, name").fetchall()
        tables = [r[1] for r in rows if r[0] == "table"]
        views = [r[1] for r in rows if r[0] == "view"]
        indexes = [r[1] for r in rows if r[0] == "index"]
        return {"tables": tables, "views": views, "indexes": indexes, "constraints": [], "objects": [{"type": r[0], "name": r[1], "sql": r[2]} for r in rows]}
