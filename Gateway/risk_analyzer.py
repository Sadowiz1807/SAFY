from __future__ import annotations

from dataclasses import dataclass, field
import re

from .sql_classifier import (
    ADMIN_SECURITY,
    ALTER,
    CREATE,
    CROSS_DATABASE_OR_SERVER_LEVEL,
    DELETE,
    DROP,
    GRANT,
    INSERT,
    MERGE,
    MULTI_STATEMENT,
    RENAME,
    REVOKE,
    SELECT,
    TRANSACTION_CONTROL,
    TRUNCATE,
    UNKNOWN,
    UPDATE,
    SQLClassification,
)
from .statement_target_extractor import TargetExtraction


@dataclass(frozen=True)
class RiskAnalysis:
    risk_level: str
    risk_reasons: list[str] = field(default_factory=list)
    requires_confirmation: bool = False
    requires_workspace_lock: bool = False
    requires_audit_prewrite: bool = True
    invalidates_schema_snapshot: bool = False
    blocked_by_policy: bool = False


def analyze_risk(classification: SQLClassification, targets: TargetExtraction) -> RiskAnalysis:
    stype = classification.statement_type
    reasons = list(classification.reasons) + list(targets.warnings)
    sql = classification.normalized.normalized_sql.upper()

    if stype in {MULTI_STATEMENT, ADMIN_SECURITY, CROSS_DATABASE_OR_SERVER_LEVEL, GRANT, REVOKE}:
        return RiskAnalysis("critical", reasons + ["blocked_statement_class"], True, False, True, False, True)
    if stype == UNKNOWN:
        return RiskAnalysis("critical", reasons + ["unknown_fails_closed"], False, False, True, False, True)
    if stype in {DROP, TRUNCATE}:
        return RiskAnalysis("critical", reasons + ["destructive_schema_change_blocked"], True, True, True, True, True)
    if stype in {ALTER, RENAME}:
        return RiskAnalysis("high", reasons + ["schema_mutation_requires_sandbox"], False, True, True, True, False)
    if stype == CREATE:
        return RiskAnalysis("high", reasons + ["schema_mutation_requires_sandbox"], False, True, True, True, False)
    if stype in {UPDATE, DELETE, MERGE}:
        broad = not re.search(r"\bWHERE\b", sql)
        if broad:
            return RiskAnalysis("critical", reasons + ["broad_mutation_without_where_blocked"], True, True, True, True, True)
        return RiskAnalysis("high", reasons + ["row_mutation_requires_sandbox"], False, True, True, False, False)
    if stype == INSERT:
        return RiskAnalysis("medium", reasons + ["data_mutation"], False, False, True, False, False)
    if stype == TRANSACTION_CONTROL:
        return RiskAnalysis("medium", reasons + ["transaction_control"], False, False, True, False, False)
    if stype == SELECT:
        return RiskAnalysis("low", reasons, False, False, True, False, False)
    return RiskAnalysis("critical", reasons + ["conservative_default_block"], False, False, True, False, True)
