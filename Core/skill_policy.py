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
        if policy.get("sandbox_only") is not True or policy.get("sql_guard_required") is not True or policy.get("audit_required") is not True:
            raise ValueError("SKILL_POLICY_INVALID:required_true_flags")
        return cls(policy)

    def allows_tool(self, tool_name: str) -> bool:
        return tool_name in self.data["allowed_tools"] and tool_name not in self.data["denied_tools"]

    def allows_target(self, target: str) -> bool:
        return target in self.data["allowed_targets"] and (not self.data["sandbox_only"] or target == "sandbox")

    def allows_intent(self, intent: str) -> bool:
        return intent in self.data["allowed_intents"]
