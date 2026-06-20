from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolMetadata:
    name: str
    toolset: str = "default"
    description: str = ""
    risk_class: str = "UNKNOWN_RISK"
    read_only: bool = False
    writes_database: bool = False
    requires_sandbox: bool = False
    requires_confirmation: bool = False
    touches_secret: bool = False
    schema: dict[str, Any] = field(default_factory=dict)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int | None = None
    audit_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "toolset": self.toolset,
            "description": self.description,
            "risk_class": self.risk_class,
            "read_only": self.read_only,
            "writes_database": self.writes_database,
            "requires_sandbox": self.requires_sandbox,
            "requires_confirmation": self.requires_confirmation,
            "touches_secret": self.touches_secret,
            "schema": self.schema,
            "input_schema": self.input_schema or self.schema,
            "output_schema": self.output_schema,
            "timeout_seconds": self.timeout_seconds,
            "audit_required": self.audit_required,
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}
        self._metadata: dict[str, ToolMetadata] = {}

    def register(self, tool, metadata: ToolMetadata | dict[str, Any] | None = None) -> None:
        name = getattr(tool, "name", None)
        if not name:
            raise ValueError("tool_missing_name")
        if name in self._tools:
            raise ValueError("duplicate_tool")
        self._tools[name] = tool
        self._metadata[name] = self._coerce_metadata(tool, metadata)

    def _coerce_metadata(self, tool, metadata: ToolMetadata | dict[str, Any] | None) -> ToolMetadata:
        if isinstance(metadata, ToolMetadata):
            return metadata
        data = dict(metadata or {})
        name = data.get("name") or getattr(tool, "name", "")
        toolset = data.get("toolset") or getattr(tool, "toolset", "default")
        return ToolMetadata(
            name=name,
            toolset=toolset,
            description=data.get("description") or getattr(tool, "description", ""),
            risk_class=data.get("risk_class") or getattr(tool, "risk_class", "UNKNOWN_RISK"),
            read_only=bool(data.get("read_only", getattr(tool, "read_only", False))),
            writes_database=bool(data.get("writes_database", getattr(tool, "writes_database", False))),
            requires_sandbox=bool(data.get("requires_sandbox", getattr(tool, "requires_sandbox", False))),
            requires_confirmation=bool(data.get("requires_confirmation", getattr(tool, "requires_confirmation", False))),
            touches_secret=bool(data.get("touches_secret", getattr(tool, "touches_secret", False))),
            schema=data.get("schema") or getattr(tool, "schema", {}),
            input_schema=data.get("input_schema") or getattr(tool, "input_schema", data.get("schema") or getattr(tool, "schema", {})),
            output_schema=data.get("output_schema") or getattr(tool, "output_schema", {}),
            timeout_seconds=data.get("timeout_seconds", getattr(tool, "timeout_seconds", None)),
            audit_required=bool(data.get("audit_required", getattr(tool, "audit_required", True))),
        )

    def get(self, name: str):
        if name not in self._tools:
            raise ValueError("TOOL_NOT_FOUND")
        return self._tools[name]

    def metadata(self, name: str) -> ToolMetadata:
        if name not in self._metadata:
            raise ValueError("TOOL_NOT_FOUND")
        return self._metadata[name]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def describe(self) -> list[dict[str, Any]]:
        return [self._metadata[name].to_dict() for name in self.names()]

    def toolsets(self) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for name, meta in self._metadata.items():
            grouped.setdefault(meta.toolset, []).append(name)
        return {key: sorted(value) for key, value in sorted(grouped.items())}
