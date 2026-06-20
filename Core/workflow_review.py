from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from Core.workflow_policy import (
    DESTRUCTIVE_SQL,
    READ_ONLY_SQL,
    SECRET_ACCESS,
    UNKNOWN_RISK,
    WRITE_SQL,
    DDL_SQL,
    WorkflowPlan,
)


@dataclass
class ReviewFinding:
    reviewer: str
    status: str
    message: str
    severity: str = "info"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reviewer": self.reviewer,
            "status": self.status,
            "severity": self.severity,
            "message": self.message,
            "metadata": self.metadata,
        }


@dataclass
class WorkflowReview:
    ok: bool
    findings: list[ReviewFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "findings": [finding.to_dict() for finding in self.findings],
        }


class WorkflowReviewCoordinator:
    """Deterministic reviewer layer modeled after Hermes delegation.

    SAFY uses reviewers as local subagents with no direct execution authority.
    They inspect plan/check/result metadata and can veto unsafe routes, but they
    never run SQL themselves.
    """

    def review(self, *, plan: WorkflowPlan, check: dict[str, Any] | None = None, result: dict[str, Any] | None = None, context: dict[str, Any] | None = None) -> WorkflowReview:
        findings: list[ReviewFinding] = []
        findings.extend(self._policy_review(plan, check))
        findings.extend(self._state_review(plan, context or {}))
        findings.extend(self._result_review(plan, result))
        ok = not any(f.status == "block" for f in findings)
        return WorkflowReview(ok=ok, findings=findings)

    def _policy_review(self, plan: WorkflowPlan, check: dict[str, Any] | None) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        if plan.action_class == READ_ONLY_SQL:
            if plan.requires_sandbox:
                findings.append(ReviewFinding("policy_reviewer", "block", "READ_ONLY_SQL must not require sandbox validation.", "high"))
            if not plan.can_auto_execute:
                findings.append(ReviewFinding("policy_reviewer", "warn", "READ_ONLY_SQL should be eligible for direct read after SQL Guard.", "medium"))
        if plan.action_class in {WRITE_SQL, DDL_SQL}:
            if not plan.requires_sandbox:
                findings.append(ReviewFinding("policy_reviewer", "block", "WRITE/DDL SQL must require sandbox validation.", "high"))
            if plan.can_auto_execute:
                findings.append(ReviewFinding("policy_reviewer", "block", "WRITE/DDL SQL must not auto-execute from chat.", "high"))
        if plan.action_class in {DESTRUCTIVE_SQL, SECRET_ACCESS, UNKNOWN_RISK} and plan.can_auto_execute:
            findings.append(ReviewFinding("policy_reviewer", "block", f"{plan.action_class} cannot auto-execute.", "high"))
        if check:
            if plan.action_class == READ_ONLY_SQL and check.get("sandbox_check", {}).get("executed_in_sandbox") is True:
                findings.append(ReviewFinding("guard_reviewer", "block", "Read-only check unexpectedly executed in sandbox.", "high"))
            if check.get("error_code"):
                findings.append(ReviewFinding("guard_reviewer", "warn", str(check.get("error_code")), "medium"))
        if not findings:
            findings.append(ReviewFinding("policy_reviewer", "pass", "Workflow route matches SAFY SQL policy."))
        return findings

    def _state_review(self, plan: WorkflowPlan, context: dict[str, Any]) -> list[ReviewFinding]:
        target = context.get("target")
        database_profile_id = context.get("database_profile_id")
        findings: list[ReviewFinding] = []
        if plan.route in {"direct_read", "sandbox_then_real"} and target == "connected_database" and not database_profile_id:
            findings.append(ReviewFinding("state_reviewer", "block", "Connected database route has no database_profile_id.", "high"))
        if not findings:
            findings.append(ReviewFinding("state_reviewer", "pass", "Required routing context is present."))
        return findings

    def _result_review(self, plan: WorkflowPlan, result: dict[str, Any] | None) -> list[ReviewFinding]:
        if not result:
            return [ReviewFinding("result_reviewer", "pass", "No result to review yet.")]
        if plan.action_class == READ_ONLY_SQL and result.get("rows") and result.get("result_rows_persisted"):
            return [ReviewFinding("result_reviewer", "block", "Read-only rows must remain display-only and must not persist as session state.", "high")]
        if result.get("error") or result.get("code"):
            return [ReviewFinding("result_reviewer", "warn", str(result.get("message") or result.get("code") or "execution warning"), "medium")]
        return [ReviewFinding("result_reviewer", "pass", "Result metadata is acceptable.")]
