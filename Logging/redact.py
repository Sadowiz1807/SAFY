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

SQL_LEADING_RE = re.compile(
    r"^\s*(?:/\*.*?\*/\s*)*(?:SELECT|WITH|INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|BEGIN|COMMIT|ROLLBACK|SET)\b",
    re.I | re.S,
)
SENSITIVE_SQL_IDENTIFIER_RE = re.compile(
    r"\b(?:password|passwd|api[_-]?key|apikey|token|secret|credential|private[_-]?key|access[_-]?key)\b",
    re.I,
)
SQL_SINGLE_QUOTED_LITERAL_RE = re.compile(r"(?:E|U&)?'(?:''|[^'])*'", re.I)
SQL_DOLLAR_QUOTED_LITERAL_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)?\$.*?\$\1\$", re.S)
SQL_SENSITIVE_NUMERIC_ASSIGNMENT_RE = re.compile(
    r"(\b(?:password|passwd|api[_-]?key|apikey|token|secret|credential|private[_-]?key|access[_-]?key)\b\s*=\s*)([-+]?\d+(?:\.\d+)?)",
    re.I,
)


def redact_sql_sensitive_literals(value: str) -> str:
    """Redact SQL literals when a statement references credential-like fields.

    Non-sensitive SQL remains intact so session draft restoration continues to
    work. For sensitive statements, all string literals are removed because a
    neighboring WHERE/value literal can also disclose an identifier or secret.
    """
    text = str(value)
    if not SQL_LEADING_RE.search(text) or not SENSITIVE_SQL_IDENTIFIER_RE.search(text):
        return text
    text = SQL_DOLLAR_QUOTED_LITERAL_RE.sub("'[REDACTED]'", text)
    text = SQL_SINGLE_QUOTED_LITERAL_RE.sub("'[REDACTED]'", text)
    return SQL_SENSITIVE_NUMERIC_ASSIGNMENT_RE.sub(r"\1[REDACTED]", text)


def redact_text(value: str | None) -> str | None:
    if value is None:
        return None
    redacted = redact_sql_sensitive_literals(str(value))
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
