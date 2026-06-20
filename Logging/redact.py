from __future__ import annotations

from typing import Any
import re

SECRET_KEY_TOKENS = ("password", "passwd", "api_key", "apikey", "token", "secret", "credential")
SECRET_PATTERNS = [
    re.compile(r"((?:api[_-]?key|token|secret|password|passwd)\s*[=:]\s*)([^\s&,'\"]+)", re.I),
    re.compile(r"((?:postgres(?:ql)?|mysql)://[^:\s]+:)([^@\s]+)(@)", re.I),
    re.compile(r"(Bearer\s+)([A-Za-z0-9._\-]+)", re.I),
    re.compile(r"(?<![A-Za-z0-9_])(sk-[A-Za-z0-9_\-]{3})[A-Za-z0-9_\-]*"),
]


def redact_text(value: str | None) -> str | None:
    if value is None:
        return None
    redacted = str(value)
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 3:
            redacted = pattern.sub(r"\1[REDACTED]\3", redacted)
        elif pattern.groups == 2:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def redact_obj(value: Any) -> Any:
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            if any(token in key.lower() for token in SECRET_KEY_TOKENS):
                output[key] = "[REDACTED]"
            else:
                output[key] = redact_obj(item)
        return output
    if isinstance(value, list):
        return [redact_obj(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
