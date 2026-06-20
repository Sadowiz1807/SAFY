from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

STATES = {"created", "starting", "restoring", "ready", "failed", "stopping", "stopped", "deleting", "deleted"}
TRANSITIONS = {
    "created": {"starting", "deleting"},
    "starting": {"restoring", "ready", "failed"},
    "restoring": {"ready", "failed"},
    "ready": {"stopping", "deleting"},
    "stopping": {"stopped"},
    "stopped": {"starting", "deleting"},
    "failed": {"deleting"},
    "deleting": {"deleted"},
    "deleted": set(),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class SandboxRecord:
    sandbox_id: str = "sandbox_default"
    name: str = "Default sandbox"
    project_id: str = "project_default"
    workspace_id: str = "workspace_default"
    dbms: str = "sqlite"
    provider_compatibility: str = "self_hosted"
    source_kind: str | None = None
    source_ref: str | None = None
    state: str = "created"
    active: bool = False
    read_only: bool = True
    write_sandbox_mode: bool = False
    future_write_mode_allowed: bool = False
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    created_by: str | None = None
    container_ref: str | None = None
    runtime_handle: dict[str, Any] = field(default_factory=dict)
    readonly_credential_ref: str | None = None
    schema_cache_path: str | None = None
    restore_job_path: str | None = None
    last_error_code: str | None = None
    policy: dict[str, Any] = field(default_factory=lambda: {"read_only": True, "write_sandbox_mode": False, "max_returned_rows": 100})

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["schema_cache_available"] = bool(self.schema_cache_path)
        return data


def assert_transition(old: str, new: str) -> None:
    if old not in STATES or new not in STATES or new not in TRANSITIONS[old]:
        raise ValueError(f"INVALID_SANDBOX_TRANSITION:{old}->{new}")
