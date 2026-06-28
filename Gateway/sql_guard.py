from __future__ import annotations

from dataclasses import dataclass, field

from .risk_analyzer import RiskAnalysis
from .sql_classifier import ADMIN_SECURITY, CROSS_DATABASE_OR_SERVER_LEVEL, MULTI_STATEMENT, UNKNOWN, SQLClassification

ALLOW_READ_ONLY = "ALLOW_READ_ONLY"
ALLOW_WITH_WARNING = "ALLOW_WITH_WARNING"
REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
BLOCK_POLICY = "BLOCK_POLICY"
BLOCK_PERMISSION = "BLOCK_PERMISSION"
BLOCK_UNKNOWN = "BLOCK_UNKNOWN"


@dataclass(frozen=True)
class GuardDecision:
    decision: str
    safety_status: str
    warnings: list[str] = field(default_factory=list)
    policy_version: str = "sql-guard-v1"


def evaluate_sql_guard(classification: SQLClassification, risk: RiskAnalysis, execution_path: str = "user_query") -> GuardDecision:
    warnings = list(risk.risk_reasons)
    if classification.statement_type == UNKNOWN:
        return GuardDecision(BLOCK_UNKNOWN, "blocked", warnings + ["unknown_statement_blocked"])
    if classification.statement_type == MULTI_STATEMENT:
        return GuardDecision(BLOCK_POLICY, "blocked", warnings + ["multi_statement_blocked"])
    if classification.statement_type in {ADMIN_SECURITY, CROSS_DATABASE_OR_SERVER_LEVEL} or risk.blocked_by_policy:
        return GuardDecision(BLOCK_POLICY, "blocked", warnings + ["policy_blocked"])
    if execution_path == "agent" and not classification.is_read_only:
        return GuardDecision(BLOCK_PERMISSION, "blocked", warnings + ["agent_path_read_only"])
    if risk.requires_confirmation:
        return GuardDecision(REQUIRE_CONFIRMATION, "requires_confirmation", warnings)
    if classification.is_read_only:
        return GuardDecision(ALLOW_READ_ONLY, "allowed", warnings)
    return GuardDecision(ALLOW_WITH_WARNING, "allowed_with_warning", warnings)
