from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillResult:
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls, **data: Any) -> "SkillResult":
        return cls(True, data=data)

    @classmethod
    def fail(cls, code: str, message: str, **details: Any) -> "SkillResult":
        return cls(False, error={"code": code, "message": message, "details": details})
