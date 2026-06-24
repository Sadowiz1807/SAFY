from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class SkillInput:
    message: str
    context: Any
    state: Any
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    success: bool
    skill: str
    action: str
    answer: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: dict[str, Any] | None = None


class SkillActionHandler(Protocol):
    """Callable contract for a shared SAFY action bound to a document skill."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...
