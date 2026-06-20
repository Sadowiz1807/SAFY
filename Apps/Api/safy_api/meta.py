from __future__ import annotations

from datetime import datetime, timezone
import uuid


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request_meta(request_id: str | None = None) -> dict[str, str]:
    return {
        "request_id": request_id or f"req_{uuid.uuid4().hex}",
        "timestamp": now_iso(),
    }
