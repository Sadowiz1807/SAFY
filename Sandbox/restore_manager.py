from __future__ import annotations

from pathlib import Path
import gzip
import shutil
import sqlite3

SUPPORTED_POSTGRES_EXT = {".sql", ".dump", ".backup"}

class RestoreManager:
    def __init__(self, sandbox_dir: Path):
        self.sandbox_dir = sandbox_dir

    def validate_source(self, source_path: str | None) -> Path | None:
        if not source_path:
            return None
        path = Path(source_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError("BLOCKED_BACKUP_MISSING")
        return path

    def restore_sqlite(self, source_path: str | None) -> Path:
        target = self.sandbox_dir / "runtime.sqlite3"
        source = self.validate_source(source_path)
        if source:
            shutil.copyfile(source, target)
        else:
            with sqlite3.connect(target) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS sandbox_runtime_items (id INTEGER PRIMARY KEY, name TEXT)")
                conn.execute("INSERT OR IGNORE INTO sandbox_runtime_items(id, name) VALUES (1, 'demo')")
        return target

    def classify_postgres_backup(self, source_path: str) -> str:
        path = self.validate_source(source_path)
        assert path is not None
        name = path.name.lower()
        if name.endswith(".backup.gz"):
            return "postgres_backup_gzip"
        if path.suffix.lower() in SUPPORTED_POSTGRES_EXT:
            return "postgres_backup"
        raise ValueError("UNSUPPORTED_BACKUP_FORMAT")

    def decompress_gzip_to_tmp(self, source_path: str) -> Path:
        source = self.validate_source(source_path)
        assert source is not None
        target = self.sandbox_dir / source.name.removesuffix(".gz")
        with gzip.open(source, "rb") as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        return target
