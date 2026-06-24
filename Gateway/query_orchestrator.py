from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import threading
import uuid

from Audit.audit_store import AuditStore
from State.high_risk_code_state import HighRiskCodeState
from State.runtime_db import RuntimeDB

from .connected_db_adapter import AdapterError, adapter_for_profile
from .db_drivers import execute_readonly as driver_execute_readonly
from .db_drivers import execute_user_sql as driver_execute_user_sql
from .db_drivers.errors import DriverError
from .permission_checker import CREDENTIAL_PERMISSIONS, DISABLED, READ_ONLY, evaluate_permission
from .real_db_policy import real_db_policy
from .risk_analyzer import RiskAnalysis, analyze_risk
from .sandbox_adapter import SandboxAdapter
from .sql_classifier import (
    ADMIN_SECURITY,
    BATCH,
    CROSS_DATABASE_OR_SERVER_LEVEL,
    DROP,
    GRANT,
    MULTI_STATEMENT,
    REVOKE,
    SELECT,
    SESSION_CONTROL,
    TRANSACTION_CONTROL,
    TRUNCATE,
    UNKNOWN,
    SQLClassification,
    classify_sql,
)
from .sql_guard import BLOCK_PERMISSION, evaluate_sql_guard
from .statement_target_extractor import TargetExtraction, extract_targets
from Sandbox.sandbox_manager import SandboxError, SandboxManager


@dataclass(frozen=True)
class QueryOrchestratorContext:
    runtime_dir: Path
    test_runtime_mode: bool = False


class QueryOrchestrator:
    MAX_USER_BATCH_STATEMENTS = 64

    def __init__(self, context: QueryOrchestratorContext):
        self.context = context
        self.checks: dict[str, dict] = {}
        self.high_risk = HighRiskCodeState(ttl_seconds=600)
        self.runtime_db = RuntimeDB(context.runtime_dir / "runtime.sqlite3")
        self.audit = AuditStore(context.runtime_dir / "audit.sqlite3")
        self.adapter = SandboxAdapter()
        self.sandbox_manager: SandboxManager | None = None
        # Real execution is serialized so a one-time check_id cannot be raced
        # by concurrent requests and applied to the database more than once.
        self._execute_lock = threading.Lock()

    @staticmethod
    def sql_hash(normalized_sql: str) -> str:
        return "hash_" + hashlib.sha256(normalized_sql.encode("utf-8")).hexdigest()

    @staticmethod
    def _execution_success_summary(payload: dict, statement_type: str | None = None) -> str:
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        driver = payload.get("driver") or metadata.get("driver") or "database"
        transport = metadata.get("execution_transport") or metadata.get("connection_kind") or "native_sql"
        stmt = (statement_type or metadata.get("statement_type") or "SQL").upper()
        row_count = payload.get("row_count", metadata.get("row_count", 0))
        if row_count is None or row_count < 0:
            row_count = 0
        return f"Execution succeeded. {stmt} completed on {driver} via {transport}. Row count: {row_count}."

    def _write_confirmation_generated_audit(self, check_id: str, sql_hash: str, target: str, confirmation_type: str | None, expires_at: str | None) -> None:
        self.audit.write_event(
            event_type="confirmation_code_generated",
            action="confirmation_code_generated",
            check_id=check_id,
            sql_hash=sql_hash,
            metadata={
                "target": target,
                "confirmation_type": confirmation_type,
                "expires_at": expires_at,
                "sql_hash": sql_hash,
                "check_id": check_id,
            },
        )

    @staticmethod
    def _is_destructive_or_blocked_statement(statement_type: str | None) -> bool:
        return (statement_type or "").upper() in {
            DROP,
            TRUNCATE,
            GRANT,
            REVOKE,
            ADMIN_SECURITY,
            CROSS_DATABASE_OR_SERVER_LEVEL,
            UNKNOWN,
            MULTI_STATEMENT,
            TRANSACTION_CONTROL,
        }

    @staticmethod
    def _risk_level_max(levels: list[str]) -> str:
        rank = {"safe": 0, "low": 0, "medium": 1, "warning": 1, "high": 2, "critical": 3}
        return max(levels or ["critical"], key=lambda value: rank.get(str(value).lower(), 3))

    def _analyze_execute_box_sql(self, sql: str) -> tuple[SQLClassification, TargetExtraction, RiskAnalysis, dict | None]:
        """Analyze one statement or a user-controlled batch for the Execute Box.

        The general SQL guard remains fail-closed for multiple statements. The
        Execute Box is a distinct, explicit user workflow, so it may accept a
        bounded batch only when every child statement is independently
        classifiable, policy-allowed, and sandbox-validatable.
        """
        classification = classify_sql(sql)
        if classification.statement_type != MULTI_STATEMENT:
            targets = extract_targets(classification)
            return classification, targets, analyze_risk(classification, targets), None

        raw_statements = classification.normalized.statements
        batch_info: dict = {
            "statement_count": len(raw_statements),
            "statement_types": [],
            "blocked_statement_indexes": [],
            "block_code": None,
            "block_message": None,
        }
        if len(raw_statements) > self.MAX_USER_BATCH_STATEMENTS:
            batch_info.update(
                {
                    "block_code": "SQL_BATCH_TOO_LARGE",
                    "block_message": f"A maximum of {self.MAX_USER_BATCH_STATEMENTS} statements is allowed in one Execute Box batch.",
                }
            )

        child_risks: list[RiskAnalysis] = []
        combined_targets: list[str] = []
        combined_target_warnings: list[str] = []
        combined_reasons: list[str] = ["multi_statement_user_batch_detected"]
        blocked_types = {
            DROP,
            TRUNCATE,
            GRANT,
            REVOKE,
            ADMIN_SECURITY,
            CROSS_DATABASE_OR_SERVER_LEVEL,
            UNKNOWN,
            MULTI_STATEMENT,
            TRANSACTION_CONTROL,
            SESSION_CONTROL,
        }

        for index, statement in enumerate(raw_statements, start=1):
            child = classify_sql(statement)
            child_targets = extract_targets(child)
            child_risk = analyze_risk(child, child_targets)
            child_risks.append(child_risk)
            batch_info["statement_types"].append(child.statement_type)
            for target_name in child_targets.targets:
                if target_name not in combined_targets:
                    combined_targets.append(target_name)
            combined_target_warnings.extend(child_targets.warnings)
            combined_reasons.extend(child_risk.risk_reasons)

            # Result-producing SELECT statements are deliberately excluded from
            # write batches. Their result-set semantics differ across drivers,
            # while direct read-only execution already has a dedicated path.
            child_blocked = child.statement_type in blocked_types or child.statement_type == SELECT or child_risk.blocked_by_policy
            if child_blocked:
                batch_info["blocked_statement_indexes"].append(index)

        if batch_info["blocked_statement_indexes"] and not batch_info.get("block_code"):
            types = set(batch_info["statement_types"])
            if types & {DROP, TRUNCATE}:
                batch_info.update(
                    {
                        "block_code": "DESTRUCTIVE_SQL_BLOCKED",
                        "block_message": "DROP and TRUNCATE are blocked inside Execute Box batches.",
                    }
                )
            elif TRANSACTION_CONTROL in types:
                batch_info.update(
                    {
                        "block_code": "TRANSACTION_CONTROL_BLOCKED",
                        "block_message": "BEGIN, COMMIT, and ROLLBACK cannot be included in an Execute Box batch; SAFY owns the transaction boundary.",
                    }
                )
            elif SELECT in types:
                batch_info.update(
                    {
                        "block_code": "SQL_BATCH_MIXED_MODE_UNSUPPORTED",
                        "block_message": "SELECT cannot be mixed into a write/DDL Execute Box batch. Run read-only queries separately.",
                    }
                )
            else:
                batch_info.update(
                    {
                        "block_code": "SQL_POLICY_BLOCKED",
                        "block_message": "At least one statement in the batch is administrative, unknown, or otherwise blocked by policy.",
                    }
                )

        aggregate_blocked = bool(batch_info.get("block_code"))
        aggregate_risk = RiskAnalysis(
            risk_level="critical" if aggregate_blocked else self._risk_level_max([risk.risk_level for risk in child_risks]),
            risk_reasons=list(dict.fromkeys(combined_reasons + (["blocked_statement_in_batch"] if aggregate_blocked else ["batch_requires_sandbox_validation"]))),
            requires_confirmation=False,
            requires_workspace_lock=any(risk.requires_workspace_lock for risk in child_risks),
            requires_audit_prewrite=True,
            invalidates_schema_snapshot=any(risk.invalidates_schema_snapshot for risk in child_risks),
            blocked_by_policy=aggregate_blocked,
        )
        batch_classification = SQLClassification(
            statement_type=BATCH,
            normalized=classification.normalized,
            is_read_only=False,
            is_multi_statement=True,
            reasons=["multi_statement_user_batch_detected"],
        )
        return (
            batch_classification,
            TargetExtraction(
                targets=combined_targets,
                warnings=list(dict.fromkeys(combined_target_warnings)),
            ),
            aggregate_risk,
            batch_info,
        )

    def _blocked_execute_box_check_response(
        self,
        *,
        check_id: str,
        sql_hash: str,
        normalized_sql: str,
        classification,
        targets,
        risk,
        target: str,
        database_profile_id: str | None,
        sandbox_id: str | None,
        permission_mode: str,
        expires_at: datetime,
        code: str,
        message: str,
        warnings: list[str] | None = None,
        batch_info: dict | None = None,
    ) -> dict:
        reasons = list(dict.fromkeys((warnings or []) + risk.risk_reasons + [code]))
        response = {
            "check_id": check_id,
            "sql_hash": sql_hash,
            "statement_type": classification.statement_type,
            "statement_types": (batch_info or {}).get("statement_types") or [classification.statement_type],
            "statement_count": (batch_info or {}).get("statement_count") or 1,
            "target": target,
            "database_profile_id": database_profile_id,
            "sandbox_id": sandbox_id,
            "user_query_access_mode": permission_mode,
            "targets": targets.targets,
            "affected_tables": targets.targets,
            "risk_level": risk.risk_level or "critical",
            "risk_reasons": risk.risk_reasons,
            "safety_status": "blocked",
            "check_passed": False,
            "decision": "BLOCK_DESTRUCTIVE_SQL" if code == "DESTRUCTIVE_SQL_BLOCKED" else "BLOCK_POLICY",
            "warnings": reasons,
            "confirmation_required": False,
            "confirmation_code": None,
            "confirmation_code_dev_hint": None,
            "confirmation_code_length": 0,
            "confirmation_expires_at": None,
            "allowed_to_attempt": False,
            "confirmation_type": None,
            "safety_report": {"target": target, "reasons": reasons},
            "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
            "policy_version": "user-execute-box-destructive-block-v2",
            "permission_mode": permission_mode,
            "normalized_sql": normalized_sql,
            "invalidates_schema_snapshot": risk.invalidates_schema_snapshot,
            "requires_workspace_lock": risk.requires_workspace_lock,
            "requires_audit_prewrite": True,
            "runtime_preview_only": False,
            "no_real_execution": True,
            "real_db_mode": True,
            "read_only": False,
            "user_execute_box_mode": True,
            "sandbox_validated": False,
            "sandbox_check": {
                "status": "skipped",
                "sandbox_id": sandbox_id,
                "executed_in_sandbox": False,
                "reason": code,
            },
            "result_row_session_persistence_allowed": False,
            "blocked_sql_display_allowed": True,
            "blocked_message": message,
            "error_code": code,
            "blocked_statement_indexes": (batch_info or {}).get("blocked_statement_indexes") or [],
        }
        self.audit.write_event(
            event_type="user_execute_box_query_blocked",
            action="query_check",
            check_id=check_id,
            sql_hash=sql_hash,
            status="blocked",
            metadata={
                "statement_type": classification.statement_type,
                "decision": response["decision"],
                "database_profile_id": database_profile_id,
                "sandbox_id": sandbox_id,
                "error_code": code,
            },
        )
        self.checks[check_id] = {**response, "target": target, "database_profile_id": database_profile_id, "sandbox_id": sandbox_id, "consumed": False}
        return response

    def _real_db_check(self, sql: str, target: str, database_profile_id: str | None, permission_mode: str, expose_confirmation_code: bool, database_profile: dict | None) -> dict:
        policy = real_db_policy(sql)
        check_id = f"check_real_{uuid.uuid4().hex}"
        sql_hash = self.sql_hash(policy["normalized_sql"])
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        confirmation_code_dev_hint = None
        confirmation_expires_at = None
        if policy.get("confirmation_required"):
            record = self.high_risk.generate(check_id, sql_hash, target)
            confirmation_code_dev_hint = record.code if record and expose_confirmation_code else None
            confirmation_expires_at = record.expires_at.isoformat().replace("+00:00", "Z") if record else None
            if record:
                expires_at = min(expires_at, record.expires_at)
                self._write_confirmation_generated_audit(check_id, sql_hash, target, "numeric_code", confirmation_expires_at)
        response = {
            "check_id": check_id,
            "sql_hash": sql_hash,
            "statement_type": policy["statement_type"],
            "target": target,
            "database_profile_id": database_profile_id,
            "user_query_access_mode": permission_mode,
            "targets": [],
            "affected_tables": [],
            "risk_level": "medium" if policy.get("confirmation_required") else "safe",
            "risk_reasons": policy.get("warnings", []),
            "safety_status": "requires_confirmation" if policy.get("confirmation_required") else "allowed" if policy.get("allowed") else "blocked",
            "decision": "REQUIRE_CONFIRMATION" if policy.get("confirmation_required") else "ALLOW_READ_ONLY" if policy.get("allowed") else "BLOCK_POLICY",
            "warnings": policy.get("warnings", []),
            "confirmation_required": bool(policy.get("confirmation_required")),
            "confirmation_code": None,
            "confirmation_code_dev_hint": confirmation_code_dev_hint,
            "confirmation_code_length": 4 if policy.get("confirmation_required") else 0,
            "confirmation_expires_at": confirmation_expires_at,
            "allowed_to_attempt": bool(policy.get("allowed")),
            "confirmation_type": "numeric_code" if policy.get("confirmation_required") else None,
            "safety_report": {"target": target, "reasons": policy.get("warnings", [])},
            "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
            "policy_version": "agent-real-db-readonly-v1",
            "permission_mode": permission_mode,
            "normalized_sql": policy["normalized_sql"],
            "invalidates_schema_snapshot": False,
            "requires_workspace_lock": False,
            "requires_audit_prewrite": True,
            "runtime_preview_only": False,
            "no_real_execution": False,
            "real_db_mode": True,
            "read_only": True,
            "result_row_session_persistence_allowed": False,
            "blocked_sql_display_allowed": policy.get("blocked_sql_display_allowed", False),
            "blocked_message": policy.get("blocked_message"),
            "error_code": policy.get("error_code"),
        }
        self.audit.write_event(
            event_type="real_db_query_check",
            action="query_check",
            check_id=check_id,
            sql_hash=sql_hash,
            metadata={
                "statement_type": policy["statement_type"],
                "decision": response["decision"],
                "database_profile_id": database_profile_id,
                "raw_sql_persisted": False,
            },
        )
        self.checks[check_id] = {**response, "target": target, "database_profile_id": database_profile_id, "consumed": False, "database_profile": database_profile or {}}
        return response

    def _user_execute_box_check(self, sql: str, target: str, database_profile_id: str | None, permission_mode: str, expose_confirmation_code: bool, database_profile: dict | None, sandbox_id: str | None) -> dict:
        classification, targets, risk, batch_info = self._analyze_execute_box_sql(sql)
        normalized_sql = classification.normalized.normalized_sql
        check_id = f"check_user_{uuid.uuid4().hex}"
        sql_hash = self.sql_hash(normalized_sql)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        sandbox_id = sandbox_id or (f"db_{database_profile_id}" if database_profile_id else "sandbox_default")
        if permission_mode == DISABLED:
            return self._blocked_execute_box_check_response(
                check_id=check_id,
                sql_hash=sql_hash,
                normalized_sql=normalized_sql,
                classification=classification,
                targets=targets,
                risk=risk,
                target=target,
                database_profile_id=database_profile_id,
                sandbox_id=sandbox_id,
                permission_mode=permission_mode,
                expires_at=expires_at,
                code="DATABASE_ACCESS_DISABLED",
                message="This database profile disables user query execution.",
                warnings=["database_profile_disabled"],
                batch_info=batch_info,
            )
        if permission_mode == READ_ONLY and not classification.is_read_only:
            return self._blocked_execute_box_check_response(
                check_id=check_id,
                sql_hash=sql_hash,
                normalized_sql=normalized_sql,
                classification=classification,
                targets=targets,
                risk=risk,
                target=target,
                database_profile_id=database_profile_id,
                sandbox_id=sandbox_id,
                permission_mode=permission_mode,
                expires_at=expires_at,
                code="DATABASE_READ_ONLY",
                message="This database profile is read-only and cannot execute DDL or DML.",
                warnings=["read_only_blocks_mutation"],
                batch_info=batch_info,
            )
        if permission_mode not in {READ_ONLY, CREDENTIAL_PERMISSIONS}:
            return self._blocked_execute_box_check_response(
                check_id=check_id,
                sql_hash=sql_hash,
                normalized_sql=normalized_sql,
                classification=classification,
                targets=targets,
                risk=risk,
                target=target,
                database_profile_id=database_profile_id,
                sandbox_id=sandbox_id,
                permission_mode=permission_mode,
                expires_at=expires_at,
                code="DATABASE_PERMISSION_MODE_INVALID",
                message="The database profile has an unsupported query access mode.",
                warnings=["unknown_permission_mode"],
                batch_info=batch_info,
            )

        if risk.blocked_by_policy or self._is_destructive_or_blocked_statement(classification.statement_type):
            if batch_info and batch_info.get("block_code"):
                code = str(batch_info["block_code"])
                message = str(batch_info.get("block_message") or "SQL batch policy blocked execution.")
            elif classification.statement_type in {DROP, TRUNCATE}:
                code = "DESTRUCTIVE_SQL_BLOCKED"
                message = "Destructive SQL is blocked by SAFY policy. Create a reviewed migration or enable a separate administrative workflow."
            elif classification.statement_type == TRANSACTION_CONTROL:
                code = "TRANSACTION_CONTROL_BLOCKED"
                message = "Transaction-control statements are not supported in the Execute Box. Submit the DDL/DML statement itself; SAFY manages sandbox and real-database transactions."
            else:
                code = "SQL_POLICY_BLOCKED"
                message = "SQL policy blocks this statement before sandbox validation."
            return self._blocked_execute_box_check_response(
                check_id=check_id,
                sql_hash=sql_hash,
                normalized_sql=normalized_sql,
                classification=classification,
                targets=targets,
                risk=risk,
                target=target,
                database_profile_id=database_profile_id,
                sandbox_id=sandbox_id,
                permission_mode=permission_mode,
                expires_at=expires_at,
                code=code,
                message=message,
                batch_info=batch_info,
            )

        if classification.is_read_only:
            response = {
                "check_id": check_id,
                "sql_hash": sql_hash,
                "statement_type": classification.statement_type,
                "statement_types": [classification.statement_type],
                "statement_count": 1,
                "target": target,
                "database_profile_id": database_profile_id,
                "sandbox_id": sandbox_id,
                "user_query_access_mode": permission_mode,
                "targets": targets.targets,
                "affected_tables": targets.targets,
                "risk_level": "safe",
                "risk_reasons": risk.risk_reasons,
                "safety_status": "read_only_verified",
                "check_passed": True,
                "decision": "ALLOW_READ_ONLY_DIRECT",
                "warnings": list(dict.fromkeys(risk.risk_reasons + ["read_only_query_sandbox_skipped"])),
                "confirmation_required": False,
                "confirmation_code": None,
                "confirmation_code_dev_hint": None,
                "confirmation_code_length": 0,
                "confirmation_expires_at": None,
                "allowed_to_attempt": True,
                "confirmation_type": None,
                "safety_report": {"target": target, "reasons": ["read_only_query_sandbox_skipped"]},
                "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
                "policy_version": "user-execute-box-readonly-direct-v1",
                "permission_mode": permission_mode,
                "normalized_sql": normalized_sql,
                "invalidates_schema_snapshot": False,
                "requires_workspace_lock": False,
                "requires_audit_prewrite": True,
                "runtime_preview_only": False,
                "no_real_execution": False,
                "real_db_mode": True,
                "read_only": True,
                "read_only_direct": True,
                "user_execute_box_mode": False,
                "sandbox_validated": False,
                "sandbox_check": {
                    "status": "skipped",
                    "sandbox_id": sandbox_id,
                    "executed_in_sandbox": False,
                    "reason": "read_only_query_uses_connected_database_directly",
                },
                "result_row_session_persistence_allowed": False,
                "blocked_sql_display_allowed": True,
                "blocked_message": None,
                "error_code": None,
            }
            self.audit.write_event(
                event_type="user_execute_box_readonly_check",
                action="query_check",
                check_id=check_id,
                sql_hash=sql_hash,
                metadata={
                    "statement_type": classification.statement_type,
                    "decision": response["decision"],
                    "database_profile_id": database_profile_id,
                    "sandbox_id": sandbox_id,
                    "sandbox_executed": False,
                },
            )
            self.checks[check_id] = {**response, "target": target, "database_profile_id": database_profile_id, "sandbox_id": sandbox_id, "consumed": False, "database_profile": database_profile or {}}
            return response

        sandbox_payload: dict
        try:
            if not self.sandbox_manager:
                raise SandboxError("SANDBOX_MANAGER_UNAVAILABLE", "Sandbox manager is not configured.")
            sandbox_payload = self.sandbox_manager.execute_validation(sandbox_id, normalized_sql)
            sandbox_status = "passed"
            safety_status = "sandbox_passed"
            decision = "ALLOW_AFTER_SANDBOX"
            allowed = True
            warnings = list(dict.fromkeys(risk.risk_reasons + ["sandbox_validation_passed"]))
            error_code = None
            blocked_message = None
        except SandboxError as exc:
            sandbox_payload = {"success": False, "status": "sandbox_failed", "error": {"code": exc.code, "message": str(exc), "details": exc.details}}
            sandbox_status = "failed"
            safety_status = "blocked"
            decision = "BLOCK_SANDBOX_FAILED"
            allowed = False
            warnings = list(dict.fromkeys(risk.risk_reasons + [exc.code]))
            error_code = exc.code or "SANDBOX_VALIDATION_FAILED"
            blocked_message = f"Sandbox validation failed: {str(exc)}"

        response = {
            "check_id": check_id,
            "sql_hash": sql_hash,
            "statement_type": classification.statement_type,
            "statement_types": (batch_info or {}).get("statement_types") or [classification.statement_type],
            "statement_count": (batch_info or {}).get("statement_count") or 1,
            "target": target,
            "database_profile_id": database_profile_id,
            "sandbox_id": sandbox_id,
            "user_query_access_mode": permission_mode,
            "targets": targets.targets,
            "affected_tables": targets.targets,
            "risk_level": "safe" if allowed and risk.risk_level == "low" else risk.risk_level,
            "risk_reasons": risk.risk_reasons,
            "safety_status": safety_status,
            "check_passed": allowed,
            "decision": decision,
            "warnings": list(dict.fromkeys(warnings + ["explicit_execute_button_is_confirmation_boundary"])),
            "confirmation_required": False,
            "confirmation_code": None,
            "confirmation_code_dev_hint": None,
            "confirmation_code_length": 0,
            "confirmation_expires_at": None,
            "allowed_to_attempt": allowed,
            "confirmation_type": None,
            "safety_report": {"target": target, "reasons": warnings},
            "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
            "policy_version": "user-execute-box-sandbox-then-real-v1",
            "permission_mode": permission_mode,
            "normalized_sql": normalized_sql,
            "invalidates_schema_snapshot": risk.invalidates_schema_snapshot,
            "requires_workspace_lock": risk.requires_workspace_lock,
            "requires_audit_prewrite": risk.requires_audit_prewrite,
            "runtime_preview_only": False,
            "no_real_execution": False,
            "real_db_mode": True,
            "read_only": False,
            "user_execute_box_mode": True,
            "sandbox_validated": allowed,
            "sandbox_check": {
                "status": sandbox_status,
                "sandbox_id": sandbox_id,
                "executed_in_sandbox": True,
                "result": sandbox_payload,
            },
            "result_row_session_persistence_allowed": False,
            "blocked_sql_display_allowed": True,
            "blocked_message": blocked_message,
            "error_code": error_code,
            "blocked_statement_indexes": (batch_info or {}).get("blocked_statement_indexes") or [],
        }
        self.audit.write_event(event_type="user_execute_box_query_check", action="query_check", check_id=check_id, sql_hash=sql_hash, metadata={"statement_type": classification.statement_type, "decision": decision, "database_profile_id": database_profile_id, "sandbox_id": sandbox_id})
        self.checks[check_id] = {**response, "target": target, "database_profile_id": database_profile_id, "sandbox_id": sandbox_id, "consumed": False, "database_profile": database_profile or {}}
        return response

    def check(self, sql: str, target: str, database_profile_id: str | None, permission_mode: str, execution_path: str = "user_query", expose_confirmation_code: bool = False, real_db_mode: bool = False, database_profile: dict | None = None, sandbox_id: str | None = None) -> dict:
        if real_db_mode and target == "connected_database" and execution_path == "execute_box_user":
            return self._user_execute_box_check(sql, target, database_profile_id, permission_mode, expose_confirmation_code, database_profile, sandbox_id)
        if real_db_mode:
            return self._real_db_check(sql, target, database_profile_id, permission_mode, expose_confirmation_code, database_profile)
        if target == "sandbox" and not sandbox_id:
            sandbox_id = "sandbox_default"
        # Sandbox checks intentionally use metadata/SQL Guard only; no DB/container connection happens here.
        classification = classify_sql(sql)
        targets = extract_targets(classification)
        risk = analyze_risk(classification, targets)
        guard = evaluate_sql_guard(classification, risk, execution_path=execution_path)
        permission = evaluate_permission(guard, classification.is_read_only, permission_mode, execution_path=execution_path)
        decision = permission.decision if permission.allowed else BLOCK_PERMISSION
        safety_status = guard.safety_status if permission.allowed else "blocked"
        warnings = list(dict.fromkeys(guard.warnings + permission.reasons))
        check_id = f"check_{uuid.uuid4().hex}"
        sql_hash = self.sql_hash(classification.normalized.normalized_sql)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        confirmation_required = decision == "REQUIRE_CONFIRMATION"
        confirmation_code_dev_hint = None
        confirmation_expires_at = None
        if confirmation_required:
            record = self.high_risk.generate(check_id, sql_hash, target)
            confirmation_code_dev_hint = record.code if record and expose_confirmation_code else None
            confirmation_expires_at = record.expires_at.isoformat().replace("+00:00", "Z") if record else None
            if record:
                expires_at = min(expires_at, record.expires_at)
                self._write_confirmation_generated_audit(check_id, sql_hash, target, "numeric_code", confirmation_expires_at)

        response = {
            "check_id": check_id,
            "sql_hash": sql_hash,
            "statement_type": classification.statement_type,
            "target": target,
            "database_profile_id": database_profile_id,
            "sandbox_id": sandbox_id,
            "user_query_access_mode": permission_mode,
            "targets": targets.targets,
            "affected_tables": targets.targets,
            "risk_level": "safe" if risk.risk_level == "low" else risk.risk_level,
            "risk_reasons": risk.risk_reasons,
            "safety_status": safety_status,
            "decision": decision,
            "warnings": warnings,
            "confirmation_required": confirmation_required,
            "confirmation_code": None,
            "confirmation_code_dev_hint": confirmation_code_dev_hint,
            "confirmation_code_length": 4 if confirmation_required else 0,
            "confirmation_expires_at": confirmation_expires_at,
            "allowed_to_attempt": permission.allowed,
            "confirmation_type": "numeric_code" if confirmation_required else None,
            "safety_report": {"target": target, "reasons": risk.risk_reasons},
            "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
            "policy_version": guard.policy_version,
            "permission_mode": permission_mode,
            "normalized_sql": classification.normalized.normalized_sql,
            "invalidates_schema_snapshot": risk.invalidates_schema_snapshot,
            "requires_workspace_lock": risk.requires_workspace_lock,
            "requires_audit_prewrite": risk.requires_audit_prewrite,
            "execution_available": target in {"sandbox", "connected_database"},
            "runtime_check": True,
            "sandbox_mode": target == "sandbox",
        }
        self.audit.write_event(event_type="query_check", action="query_check", check_id=check_id, sql_hash=sql_hash, metadata={"statement_type": classification.statement_type, "decision": decision})
        self.checks[check_id] = {**response, "target": target, "database_profile_id": database_profile_id, "sandbox_id": sandbox_id, "consumed": False}
        return response

    def execute(self, check_id: str | None, sql_hash: str | None, target: str, user_decision: str | None, confirmation_code: str | None, database_profile_id: str | None = None, row_limit: int = 100, sandbox_id: str | None = None) -> tuple[bool, dict]:
        with self._execute_lock:
            return self._execute_once(
                check_id=check_id,
                sql_hash=sql_hash,
                target=target,
                user_decision=user_decision,
                confirmation_code=confirmation_code,
                database_profile_id=database_profile_id,
                row_limit=row_limit,
                sandbox_id=sandbox_id,
            )

    def _execute_once(self, check_id: str | None, sql_hash: str | None, target: str, user_decision: str | None, confirmation_code: str | None, database_profile_id: str | None = None, row_limit: int = 100, sandbox_id: str | None = None) -> tuple[bool, dict]:
        if not check_id or check_id not in self.checks:
            return False, {"code": "QUERY_CHECK_REQUIRED", "message": "Run /query/check before /query/execute."}
        check = self.checks[check_id]
        if check.get("consumed"):
            return False, {"code": "QUERY_CHECK_CONSUMED", "message": "Query check has already been consumed."}
        expires_at = datetime.fromisoformat(check["expires_at"].replace("Z", "+00:00"))
        if expires_at <= datetime.now(timezone.utc):
            check["consumed"] = True
            self.checks.pop(check_id, None)
            return False, {"code": "QUERY_CHECK_EXPIRED", "message": "Run /query/check again before /query/execute."}
        if check.get("runtime_check") and target != check.get("target"):
            return False, {"code": "TARGET_MISMATCH", "message": "Target does not match the safety check."}
        if database_profile_id != check.get("database_profile_id"):
            return False, {"code": "DATABASE_PROFILE_MISMATCH", "message": "Database profile does not match the safety check."}
        if check.get("sandbox_mode"):
            if target != "sandbox":
                return False, {"code": "TARGET_MISMATCH", "message": "Sandbox safety check cannot execute against a real DB target."}
            if (sandbox_id or "sandbox_default") != check.get("sandbox_id"):
                return False, {"code": "SANDBOX_MISMATCH", "message": "Sandbox does not match the safety check."}
        elif target == "sandbox":
            return False, {"code": "TARGET_MISMATCH", "message": "Safety check target cannot execute against a different runtime target."}
        if sql_hash != check["sql_hash"]:
            return False, {"code": "SQL_HASH_MISMATCH", "message": "SQL hash does not match the safety check."}
        if user_decision == "no":
            check["consumed"] = True
            self.checks.pop(check_id, None)
            self.high_risk.consume(check_id)
            return True, {"status": "cancelled", "note": "User cancelled before SQL execution."}
        if user_decision not in {"yes", None}:
            return False, {"code": "MANUAL_CONFIRMATION_MISSING", "message": "User decision must be yes or no."}
        if check.get("confirmation_required", False) and user_decision != "yes":
            return False, {"code": "MANUAL_CONFIRMATION_MISSING", "message": "High-risk query requires explicit confirmation."}
        if check.get("safety_status") == "blocked" or str(check.get("decision", "")).startswith("BLOCK"):
            return False, {"code": check.get("error_code") or "SQL_POLICY_BLOCKED", "message": check.get("blocked_message") or "SQL policy or permission blocks execution."}
        if check.get("user_execute_box_mode"):
            if target != "connected_database":
                return False, {"code": "TARGET_MISMATCH", "message": "User Execute Box checks can only be applied to the checked connected database target."}
            if not check.get("sandbox_validated"):
                return False, {"code": "SANDBOX_VALIDATION_REQUIRED", "message": "Check Safety must pass sandbox validation before real database execution."}
            if user_decision != "yes":
                return False, {"code": "MANUAL_CONFIRMATION_MISSING", "message": "User must explicitly execute the sandbox-validated SQL."}
            try:
                # Prewrite an immutable attempt record, then consume the one-time
                # check before touching the real database. A driver/network error
                # can occur after the server committed the statement; retaining
                # the same check would make a retry capable of double-applying it.
                self.audit.write_event(
                    event_type="user_execute_box_real_db_attempt",
                    action="query_execute_pre",
                    check_id=check_id,
                    sql_hash=check["sql_hash"],
                    status="attempting",
                    metadata={
                        "database_profile_id": database_profile_id,
                        "statement_type": check.get("statement_type"),
                        "sandbox_id": check.get("sandbox_id"),
                        "sandbox_validated": True,
                        "user_controlled": True,
                        "raw_sql_persisted": False,
                    },
                )
            except Exception:
                return False, {"code": "AUDIT_PREWRITE_FAILED", "message": "Execution was blocked because the audit prewrite failed."}

            check["consumed"] = True
            self.checks.pop(check_id, None)
            self.high_risk.consume(check_id)
            try:
                payload = driver_execute_user_sql(check["normalized_sql"], check.get("database_profile") or {}, options={"row_limit": row_limit})
                metadata = payload.get("metadata", {})
                audit = self.audit.write_event(
                    event_type="user_execute_box_real_db_execute",
                    action="query_execute",
                    check_id=check_id,
                    sql_hash=check["sql_hash"],
                    status="success",
                    metadata={
                        "database_profile_id": database_profile_id,
                        "driver": payload.get("driver"),
                        "row_count": metadata.get("row_count"),
                        "statement_type": check.get("statement_type"),
                        "sandbox_id": check.get("sandbox_id"),
                        "sandbox_validated": True,
                        "user_controlled": True,
                        "result_rows_persisted": False,
                        "raw_sql_persisted": False,
                    },
                )
                payload["audit_id"] = audit["audit_id"]
                payload.setdefault("read_only", False)
                payload.setdefault("user_controlled", True)
                payload.setdefault("sandbox_validated", True)
                payload.setdefault("no_result_persistence", True)
                payload.setdefault("status", "executed")
                payload.setdefault("summary", self._execution_success_summary(payload, check.get("statement_type")))
                payload.setdefault("success_message", payload.get("summary"))
                schema_changed = bool(check.get("invalidates_schema_snapshot"))
                payload.setdefault("schema_changed", schema_changed)
                payload.setdefault("schema_refresh_required", schema_changed)
                return True, payload
            except DriverError as exc:
                self.audit.write_event(
                    event_type="user_execute_box_real_db_execute",
                    action="query_execute",
                    check_id=check_id,
                    sql_hash=check["sql_hash"],
                    status="failed",
                    metadata={
                        "database_profile_id": database_profile_id,
                        "statement_type": check.get("statement_type"),
                        "sandbox_id": check.get("sandbox_id"),
                        "error_code": exc.error_code,
                        "raw_sql_persisted": False,
                    },
                )
                return False, {"code": exc.error_code, "message": str(exc), "details": exc.details}
            except AdapterError as exc:
                error = exc.to_error()
                self.audit.write_event(
                    event_type="user_execute_box_real_db_execute",
                    action="query_execute",
                    check_id=check_id,
                    sql_hash=check["sql_hash"],
                    status="failed",
                    metadata={
                        "database_profile_id": database_profile_id,
                        "statement_type": check.get("statement_type"),
                        "sandbox_id": check.get("sandbox_id"),
                        "error_code": error.get("code"),
                        "raw_sql_persisted": False,
                    },
                )
                return False, error
        if check.get("confirmation_required", False):
            if not confirmation_code:
                return False, {"code": "MANUAL_CONFIRMATION_MISSING", "message": "High-risk confirmation code is required."}
            ok, reason = self.high_risk.validate(check_id, sql_hash or "", target, confirmation_code)
            if not ok:
                return False, {"code": "MANUAL_CONFIRMATION_INVALID", "message": "High-risk confirmation code is invalid.", "details": {"reason": reason}}
            self.audit.write_event(event_type="confirmation_code_validated", action="confirmation_code_validated", check_id=check_id, sql_hash=check["sql_hash"], metadata={"target": target, "result": reason})
        if check.get("sandbox_mode"):
            if not self.sandbox_manager:
                return False, {"code": "SANDBOX_MANAGER_UNAVAILABLE", "message": "Sandbox manager is not configured."}
            try:
                payload = self.sandbox_manager.execute_readonly(check.get("sandbox_id") or "sandbox_default", check["normalized_sql"], row_limit=row_limit)
                metadata = payload.get("metadata", {})
                self.sandbox_manager._audit(check.get("sandbox_id") or "sandbox_default").write("sandbox_query_execute", check.get("sandbox_id") or "sandbox_default", check_id=check_id, sql_hash=check["sql_hash"], row_count=metadata.get("row_count"), result_rows_persisted=False)
                payload.setdefault("read_only", True)
                payload.setdefault("no_result_persistence", True)
                check["consumed"] = True
                self.checks.pop(check_id, None)
                self.high_risk.consume(check_id)
                return True, payload
            except SandboxError as exc:
                return False, {"code": exc.code, "message": str(exc), "details": exc.details}
        if check.get("real_db_mode"):
            try:
                payload = driver_execute_readonly(check["normalized_sql"], check.get("database_profile") or {}, options={"row_limit": row_limit})
                metadata = payload.get("metadata", {})
                audit = self.audit.write_event(event_type="real_db_query_execute", action="query_execute", check_id=check_id, sql_hash=check["sql_hash"], status="success", metadata={"database_profile_id": database_profile_id, "driver": payload.get("driver"), "row_count": metadata.get("row_count"), "truncated": metadata.get("truncated"), "execution_time_ms": metadata.get("execution_time_ms"), "result_rows_persisted": False, "raw_sql_persisted": False})
                payload["audit_id"] = audit["audit_id"]
                payload.setdefault("read_only", True)
                payload.setdefault("no_result_persistence", True)
                payload.setdefault("result_rows_persisted", False)
                payload.setdefault("raw_sql_persisted", False)
                payload.setdefault("executed_sql", check.get("normalized_sql"))
                payload.setdefault("chat_display", {
                    "type": "query_result",
                    "title": "Database result",
                    "mode": "read_only_direct",
                    "sql": check.get("normalized_sql"),
                    "columns": payload.get("columns") or [],
                    "rows": payload.get("rows") or [],
                    "row_count": payload.get("row_count") or metadata.get("row_count") or len(payload.get("rows") or []),
                    "read_only": True,
                    "result_rows_persisted": False,
                })
                check["consumed"] = True
                self.checks.pop(check_id, None)
                self.high_risk.consume(check_id)
                return True, payload
            except DriverError as exc:
                return False, {"code": exc.error_code, "message": str(exc), "details": exc.details}
            except AdapterError as exc:
                return False, exc.to_error()
        lock_id = None
        try:
            if check.get("requires_audit_prewrite", False):
                self.audit.write_event(event_type="query_execute_pre", action="query_execute_pre", check_id=check_id, sql_hash=check["sql_hash"], metadata={"decision": check.get("decision")})
            if check.get("requires_workspace_lock", False):
                lock = self.runtime_db.acquire_workspace_lock(target, owner="query_gate", reason="query_execute_gate")
                if not lock:
                    return False, {"code": "WORKSPACE_LOCKED", "message": "Workspace is locked."}
                lock_id = lock["lock_id"]
            return False, {
                "code": "RUNTIME_EXECUTION_UNAVAILABLE",
                "message": "No real runtime adapter is available for this checked target. Use connected_database real_db_mode or a ready sandbox runtime.",
            }
        except Exception:
            return False, {"code": "AUDIT_PREWRITE_FAILED", "message": "Execution gate failed closed."}
        finally:
            if lock_id:
                self.runtime_db.release_workspace_lock(lock_id)
