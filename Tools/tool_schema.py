from __future__ import annotations


def require_fields(payload: dict, fields: list[str]) -> None:
    missing = [field for field in fields if field not in payload]
    if missing:
        raise ValueError("TOOL_EXECUTION_FAILED:missing_" + ",".join(missing))
