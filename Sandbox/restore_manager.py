from __future__ import annotations

from pathlib import Path
import gzip
import os
import shutil
import sqlite3

SUPPORTED_POSTGRES_EXT = {".sql", ".dump", ".backup"}

class RestoreManager:
    def __init__(self, sandbox_dir: Path):
        self.sandbox_dir = sandbox_dir
        try:
            configured = int(os.getenv("SAFY_SANDBOX_MAX_RESTORE_BYTES", str(1024 * 1024 * 1024)))
        except ValueError:
            configured = 1024 * 1024 * 1024
        self.max_restore_bytes = max(1024 * 1024, configured)

    def validate_source(self, source_path: str | None) -> Path | None:
        if not source_path:
            return None
        path = Path(source_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError("BLOCKED_BACKUP_MISSING")
        if path.stat().st_size > self.max_restore_bytes:
            raise ValueError("BACKUP_TOO_LARGE")
        return path

    def restore_sqlite(self, source_path: str | None) -> Path:
        target = self.sandbox_dir / "runtime.sqlite3"
        source = self.validate_source(source_path)
        if source:
            if source.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
                raise ValueError("UNSUPPORTED_BACKUP_FORMAT")
            # Validate before copying so arbitrary files cannot be imported into
            # a managed sandbox and later exposed as a database runtime.
            try:
                with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as conn:
                    conn.execute("PRAGMA schema_version").fetchone()
            except sqlite3.DatabaseError as exc:
                raise ValueError("INVALID_SQLITE_BACKUP") from exc
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
        total = 0
        try:
            with gzip.open(source, "rb") as src, target.open("wb") as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > self.max_restore_bytes:
                        raise ValueError("BACKUP_TOO_LARGE")
                    dst.write(chunk)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return target
