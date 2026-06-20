from __future__ import annotations

from Gateway.risk_analyzer import analyze_risk
from Gateway.sql_classifier import CREATE, classify_sql
from Gateway.sql_guard import evaluate_sql_guard
from Gateway.statement_target_extractor import extract_targets
from Tools.tool_result import ToolResult


class ValidateSQLTool:
    name = "sql.validate"
    toolset = "sql"

    def run(self, statement: str, target: str = "sandbox") -> ToolResult:
        classification = classify_sql(statement)
        targets = extract_targets(classification)
        risk = analyze_risk(classification, targets)
        guard = evaluate_sql_guard(classification, risk, execution_path="user_query")
        allowed = target == "sandbox" and classification.statement_type == CREATE and guard.decision in {"REQUIRE_CONFIRMATION", "ALLOW_WITH_WARNING"}
        if not allowed:
            return ToolResult(False, {"decision": guard.decision, "statement_type": classification.statement_type}, "SQL_BLOCKED", guard.warnings)
        return ToolResult(True, {"statement": classification.normalized.normalized_sql, "statement_type": classification.statement_type, "guard_decision": guard.decision, "targets": targets.targets}, warnings=guard.warnings)
