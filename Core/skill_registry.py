from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class RegisteredSkill:
    name: str
    runtime: Any
    description: str = ""
    actions: list[str] = field(default_factory=list)
    status: str = "active"


class SkillRegistry:
    """Runtime registry for SAFY skills.

    Existing skill classes can be registered without rewriting them. The goal is
    to make available skills explicit and inspectable before deeper refactors.
    """

    def __init__(self) -> None:
        self._skills: dict[str, RegisteredSkill] = {}

    def register(self, name: str, runtime: Any, *, description: str = "", actions: list[str] | None = None, status: str = "active") -> RegisteredSkill:
        key = self.normalize_name(name)
        item = RegisteredSkill(name=key, runtime=runtime, description=description, actions=list(actions or []), status=status)
        self._skills[key] = item
        return item

    def get(self, name: str) -> RegisteredSkill:
        key = self.normalize_name(name)
        if key not in self._skills:
            raise KeyError(f"SKILL_NOT_REGISTERED:{key}")
        return self._skills[key]

    def has(self, name: str) -> bool:
        return self.normalize_name(name) in self._skills

    def active_names(self) -> list[str]:
        return [name for name, item in self._skills.items() if item.status == "active"]

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": item.name,
                "description": item.description,
                "actions": list(item.actions),
                "status": item.status,
            }
            for item in self._skills.values()
        ]

    def call(self, name: str, method: str, *args: Any, **kwargs: Any) -> Any:
        item = self.get(name)
        fn: Callable[..., Any] | None = getattr(item.runtime, method, None)
        if not callable(fn):
            raise AttributeError(f"SKILL_METHOD_NOT_FOUND:{item.name}.{method}")
        return fn(*args, **kwargs)

    @staticmethod
    def normalize_name(name: str) -> str:
        return str(name or "").strip().lower().replace("-", "_").replace(" ", "_")
