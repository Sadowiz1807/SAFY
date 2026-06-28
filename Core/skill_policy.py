from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REQUIRED_FIELDS = {"allowed_intents", "allowed_targets", "allowed_toolsets", "allowed_tools", "denied_tools", "allowed_statement_classes", "blocked_statement_classes", "sandbox_only", "sql_guard_required", "audit_required", "max_steps", "timeout_seconds", "redaction_profile", "confirmation_behavior"}


@dataclass(frozen=True)
class SkillPolicy:
    data: dict[str, Any]
    version: str = "runtime-skill-policy-v1"

    @classmethod
    def compile(cls, frontmatter: dict[str, Any]) -> "SkillPolicy":
        policy = frontmatter.get("policy", {}) if isinstance(frontmatter, dict) else {}
        missing = sorted(REQUIRED_FIELDS - set(policy))
        if missing:
            raise ValueError("SKILL_POLICY_INVALID:" + ",".join(missing))
        if policy.get("sql_guard_required") is not True or policy.get("audit_required") is not True:
            raise ValueError("SKILL_POLICY_INVALID:required_guard_flags")
        sandbox_only = policy.get("sandbox_only") is True
        sandbox_then_real = policy.get("sandbox_then_real") is True
        if not sandbox_only and not sandbox_then_real:
            raise ValueError("SKILL_POLICY_INVALID:execution_safety_mode")
        if sandbox_then_real and "connected_database" not in policy.get("allowed_targets", []):
            raise ValueError("SKILL_POLICY_INVALID:sandbox_then_real_target")
        return cls(policy)

    def allows_tool(self, tool_name: str) -> bool:
        return tool_name in self.data["allowed_tools"] and tool_name not in self.data["denied_tools"]

    def allows_target(self, target: str) -> bool:
        if target not in self.data["allowed_targets"]:
            return False
        if self.data.get("sandbox_only"):
            return target == "sandbox"
        return bool(self.data.get("sandbox_then_real"))

    def allows_intent(self, intent: str) -> bool:
        return intent in self.data["allowed_intents"]
