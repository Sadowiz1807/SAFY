from __future__ import annotations

from pathlib import Path
import threading

_LOCKS: dict[str, threading.Lock] = {}


def acquire_workspace_lock(workspace_id: str):
    lock = _LOCKS.setdefault(workspace_id, threading.Lock())
    lock.acquire()
    return lock


def workspace_db_path(base_dir: Path, chat_id: str, workflow_id: str, workspace_id: str) -> Path:
    return base_dir / chat_id / workflow_id / workspace_id / "sandbox.sqlite3"
