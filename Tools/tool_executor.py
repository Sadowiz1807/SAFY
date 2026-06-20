from __future__ import annotations

from Logging.redact import redact_obj
from Core.skill_policy import SkillPolicy
from .registry import ToolRegistry
from .tool_result import ToolResult


class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry
        self.attempted: list[str] = []

    def execute(self, tool_name: str, policy: SkillPolicy, target: str, **kwargs) -> ToolResult:
        self.attempted.append(tool_name)
        if not policy.allows_target(target):
            return ToolResult(False, {}, "SKILL_POLICY_BLOCKED", ["target_blocked"])
        if not policy.allows_tool(tool_name):
            return ToolResult(False, {}, "TOOL_BLOCKED", ["tool_not_allowed_by_policy"])
        try:
            tool = self.registry.get(tool_name)
        except ValueError:
            return ToolResult(False, {}, "TOOL_NOT_FOUND")
        if getattr(tool, "toolset", None) not in policy.data["allowed_toolsets"]:
            return ToolResult(False, {}, "TOOL_BLOCKED", ["toolset_not_allowed_by_policy"])
        meta = self.registry.metadata(tool_name).to_dict()
        if meta.get("requires_sandbox") and not kwargs.get("sandbox_checked"):
            return ToolResult(False, {"tool": tool_name, "metadata": meta}, "TOOL_REQUIRES_SANDBOX", ["sandbox_checked_missing"])
        if meta.get("requires_confirmation") and not kwargs.get("confirmed"):
            return ToolResult(False, {"tool": tool_name, "metadata": meta}, "TOOL_REQUIRES_CONFIRMATION", ["confirmation_missing"])
        result = tool.run(target=target, **kwargs)
        result.data = redact_obj(result.data)
        result.data.setdefault("tool_metadata", meta)
        return result
