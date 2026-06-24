from __future__ import annotations

import sqlite3
from pathlib import Path

from Sandbox.sandbox_manager import SandboxManager


def ready_sqlite_sandbox(tmp_path: Path) -> tuple[SandboxManager, Path]:
    manager = SandboxManager(tmp_path)
    manager.create(
        {
            "sandbox_id": "sandbox_test",
            "name": "SQLite validation test",
            "engine": "sqlite",
            "active": True,
        }
    )
    db_path = tmp_path / "Data" / "sandboxes" / "sandbox_test" / "runtime.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite3.connect(db_path).close()
    record = manager.store.get("sandbox_test")
    record.state = "ready"
    record.runtime_handle = {"database": str(db_path)}
    manager.store.save(record)
    return manager, db_path


def test_sqlite_create_validation_is_rolled_back(tmp_path: Path) -> None:
    manager, db_path = ready_sqlite_sandbox(tmp_path)

    result = manager.execute_validation("sandbox_test", "CREATE TABLE should_not_persist (id INTEGER)")

    assert result["success"] is True
    with sqlite3.connect(db_path) as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='should_not_persist'"
        ).fetchone()
    assert table is None


def test_sqlite_insert_validation_is_rolled_back(tmp_path: Path) -> None:
    manager, db_path = ready_sqlite_sandbox(tmp_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")

    result = manager.execute_validation("sandbox_test", "INSERT INTO items(name) VALUES ('temporary')")

    assert result["success"] is True
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    assert count == 0


def test_sqlite_restore_rejects_unmanaged_source(tmp_path: Path) -> None:
    manager, _ = ready_sqlite_sandbox(tmp_path)
    outside = tmp_path.parent / "outside.sqlite3"
    sqlite3.connect(outside).close()

    import pytest
    from Sandbox.sandbox_manager import SandboxError

    with pytest.raises(SandboxError) as exc_info:
        manager.restore("sandbox_test", {"source_path": str(outside), "source_type": "sqlite"})
    assert exc_info.value.code == "BLOCKED_UNMANAGED_RESTORE_SOURCE"


def test_sqlite_restore_rejects_non_database_file(tmp_path: Path) -> None:
    manager, _ = ready_sqlite_sandbox(tmp_path)
    fixtures = tmp_path / "Data" / "TestFixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    invalid = fixtures / "not_a_database.sqlite3"
    invalid.write_text("not sqlite", encoding="utf-8")

    import pytest
    from Sandbox.sandbox_manager import SandboxError

    with pytest.raises(SandboxError) as exc_info:
        manager.restore("sandbox_test", {"source_path": str(invalid), "source_type": "sqlite"})
    assert exc_info.value.code == "INVALID_SQLITE_BACKUP"


def test_restore_manager_limits_gzip_expansion(tmp_path: Path, monkeypatch) -> None:
    import gzip
    import pytest
    from Sandbox.restore_manager import RestoreManager

    # The implementation enforces a minimum configured limit of 1 MiB.
    monkeypatch.setenv("SAFY_SANDBOX_MAX_RESTORE_BYTES", str(1024 * 1024))
    source = tmp_path / "large.backup.gz"
    with gzip.open(source, "wb") as handle:
        handle.write(b"x" * (1024 * 1024 + 1))

    manager = RestoreManager(tmp_path / "sandbox")
    manager.sandbox_dir.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="BACKUP_TOO_LARGE"):
        manager.decompress_gzip_to_tmp(str(source))
    assert not (tmp_path / "sandbox" / "large.backup").exists()


def test_postgres_sandbox_does_not_claim_ready_without_docker(tmp_path: Path, monkeypatch) -> None:
    manager = SandboxManager(tmp_path)
    manager.create({"sandbox_id": "pg_test", "engine": "postgresql", "active": True})
    monkeypatch.setattr(manager.docker, "available", lambda: False)
    monkeypatch.setattr(manager.docker, "required", lambda: False)

    import pytest
    from Sandbox.sandbox_manager import SandboxError

    with pytest.raises(SandboxError) as exc_info:
        manager.start("pg_test")
    assert exc_info.value.code == "SANDBOX_DOCKER_REQUIRED_FOR_POSTGRES"
    assert manager.store.get("pg_test").state == "failed"


def test_docker_is_used_when_available_even_if_gate_is_optional(tmp_path: Path, monkeypatch) -> None:
    from Sandbox.docker_manager import DockerSandboxManager

    docker = DockerSandboxManager(tmp_path)
    monkeypatch.setattr(docker, "available", lambda: True)
    monkeypatch.setattr(docker, "required", lambda: False)
    assert docker.require_available() == "DOCKER_AVAILABLE"
