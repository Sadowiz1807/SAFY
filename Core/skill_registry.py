from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import warnings

from .skill_loader import (
    SkillDescriptor,
    build_skill_context,
    discover_skills,
    load_skill_document,
)


@dataclass
class RegisteredSkill:
    name: str
    description: str = ""
    actions: list[str] = field(default_factory=list)
    status: str = "active"
    descriptor: SkillDescriptor | None = None
    handlers: dict[str, Callable[..., Any]] = field(default_factory=dict, repr=False)


class SkillRegistry:
    """Document-driven skill registry with shared action handlers.

    Built-in skills are discovered from ``Skills/<name>/SKILL.md``. The registry
    stores metadata and bound shared-action callables only; it does not own or
    create a dedicated runtime, process, worker, or dependency environment for
    each skill.
    """

    def __init__(self, skills_root: Path | None = None) -> None:
        self._skills: dict[str, RegisteredSkill] = {}
        self.invalid_skills: dict[str, str] = {}
        self.discover(skills_root)

    def discover(self, skills_root: Path | None = None) -> None:
        descriptors, invalid = discover_skills(
            skills_root,
            allow_legacy_lowercase=False,
        )
        self.invalid_skills = invalid

        existing_handlers = {
            name: dict(item.handlers)
            for name, item in self._skills.items()
        }
        self._skills = {}

        for desc in descriptors.values():
            status = "active" if desc.enabled else "disabled"
            handlers = existing_handlers.get(desc.name, {})
            self._skills[desc.name] = RegisteredSkill(
                name=desc.name,
                description=desc.description,
                actions=sorted(handlers),
                status=status,
                descriptor=desc,
                handlers=handlers,
            )

    def attach_actions(
        self,
        name: str,
        handlers: dict[str, Callable[..., Any]],
    ) -> RegisteredSkill:
        key = self.normalize_name(name)
        item = self.get(key)
        if item.status != "active":
            raise ValueError(f"SKILL_DISABLED:{key}")

        normalized: dict[str, Callable[..., Any]] = {}
        for action, handler in handlers.items():
            action_name = self.normalize_name(action)
            if not action_name or not callable(handler):
                raise ValueError(f"SKILL_ACTION_INVALID:{key}.{action_name}")
            normalized[action_name] = handler

        item.handlers.update(normalized)
        item.actions = sorted(item.handlers)
        return item

    def attach_runtime(
        self,
        name: str,
        runtime: Any,
        *,
        actions: list[str] | None = None,
    ) -> RegisteredSkill:
        """Compatibility adapter for omitted/legacy callers.

        The runtime object itself is not stored. Only the explicitly named bound
        methods are retained as shared action handlers.
        """
        warnings.warn(
            "attach_runtime() is deprecated; use attach_actions()",
            DeprecationWarning,
            stacklevel=2,
        )
        action_names = list(actions or [])
        handlers: dict[str, Callable[..., Any]] = {}
        for action in action_names:
            handler = getattr(runtime, action, None)
            if not callable(handler):
                raise AttributeError(f"SKILL_METHOD_NOT_FOUND:{name}.{action}")
            handlers[action] = handler
        return self.attach_actions(name, handlers)

    def register(
        self,
        name: str,
        runtime: Any = None,
        *,
        description: str = "",
        actions: list[str] | None = None,
        status: str = "active",
    ) -> RegisteredSkill:
        """Compatibility registration path.

        New built-in skills should be discovered from SKILL.md. If a legacy
        caller provides an object, only named bound methods are attached.
        """
        key = self.normalize_name(name)
        item = self._skills.get(key)
        if item is None:
            item = RegisteredSkill(
                name=key,
                description=description,
                status=status,
            )
            self._skills[key] = item
        else:
            if description:
                item.description = description
            item.status = status

        if runtime is not None:
            return self.attach_runtime(key, runtime, actions=actions)
        if actions:
            item.actions = sorted({self.normalize_name(a) for a in actions})
        return item

    def get(self, name: str) -> RegisteredSkill:
        key = self.normalize_name(name)
        if key not in self._skills:
            raise KeyError(f"SKILL_NOT_REGISTERED:{key}")
        return self._skills[key]

    def has(self, name: str) -> bool:
        return self.normalize_name(name) in self._skills

    def active_names(self) -> list[str]:
        return sorted(
            name
            for name, item in self._skills.items()
            if item.status == "active"
        )

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": item.name,
                "description": item.description,
                "actions": list(item.actions),
                "status": item.status,
                "version": item.descriptor.version if item.descriptor else None,
                "risk_level": (
                    item.descriptor.risk_level if item.descriptor else None
                ),
            }
            for item in sorted(self._skills.values(), key=lambda value: value.name)
        ]

    def call(self, name: str, action: str, *args: Any, **kwargs: Any) -> Any:
        item = self.get(name)
        action_name = self.normalize_name(action)
        handler = item.handlers.get(action_name)
        if not callable(handler):
            raise AttributeError(
                f"SKILL_METHOD_NOT_FOUND:{item.name}.{action_name}"
            )
        return handler(*args, **kwargs)

    def context_for(
        self,
        name: str,
        *,
        user_request: str = "",
        conversation_context: str = "",
        schema_context: str = "",
    ) -> str:
        item = self.get(name)
        if item.status != "active":
            raise ValueError(f"SKILL_DISABLED:{item.name}")
        if item.descriptor is None:
            raise ValueError(f"SKILL_DESCRIPTOR_MISSING:{item.name}")
        loaded = load_skill_document(item.descriptor)
        return build_skill_context(
            loaded,
            user_request=user_request,
            conversation_context=conversation_context,
            schema_context=schema_context,
        )

    @staticmethod
    def normalize_name(name: str) -> str:
        return (
            str(name or "")
            .strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )
