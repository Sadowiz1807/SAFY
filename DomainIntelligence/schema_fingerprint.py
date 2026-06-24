from __future__ import annotations

import hashlib
import json
from typing import Any

def schema_fingerprint(schema_summary: str | dict[str, Any] | None) -> str:
    if schema_summary is None:
        payload = ""
    elif isinstance(schema_summary, str):
        payload = schema_summary.strip()
    else:
        payload = json.dumps(schema_summary, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
