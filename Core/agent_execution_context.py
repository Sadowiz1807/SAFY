from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


@dataclass
class AgentExecutionContext:
    message: str
    chat_id: str | None = None
    target: str = "sandbox"
    model_profile_id: str | None = None
    database_profile_id: str | None = None
    request_id: str = field(default_factory=lambda: new_id("req"))
    workflow_id: str = field(default_factory=lambda: new_id("wf"))
    created_at: str = field(default_factory=now_iso)

    def ensure_chat_id(self) -> str:
        if not self.chat_id:
            self.chat_id = new_id("chat")
        return self.chat_id
