# Phase 4 Implementation Readiness Checklist

Status: PASS_READY_FOR_IMPLEMENTATION_AFTER_USER_APPROVAL

## Ready

- Phase 0-3 reported PASS.
- Source boundaries identified.
- Phase 4 modules are absent/incomplete, so implementation can be additive.
- Required contracts for Agent Core, Provider, Skills, SkillPolicy, ToolExecutor, and `/agent/chat` are defined.
- Planning keeps implementation dispatch blocked.

## Must Verify Immediately Before Implementation

- Re-read current git status and avoid overwriting user changes.
- Re-read `Apps/Api/safy_api/main.py`, `Apps/Api/safy_api/schemas.py`, `Gateway/query_orchestrator.py`, `Gateway/sql_guard.py`, `Gateway/permission_checker.py`, `State/runtime_db.py`, and `Audit/audit_logger.py`.
- Confirm folders to create: `Core/`, `Providers/`, `Skills/`, `Tools/`, `Tests/phase4/`.
- Confirm no implementation task is dispatched from `04_TASK_BOARD.yaml` without user approval.

## Open Implementation Decisions

- Provider transport priority: mock only first, then real provider transport in later task.
- SQL return default: keep `return_sql=false` unless user/UI requests and redaction permits.
- Sandbox backend sequence: start with existing mock/SQLite-compatible test harness, then Docker backends separately.
- Provider prompt contents: no schema/data/secrets unless minimized and redacted.

## Stop Conditions

- Need to enable connected DB DDL/DML.
- Need to call a real LLM provider before provider security contract is implemented.
- Need to write runtime/audit DB during planning.
- Need to change UI flow or high-risk confirmation behavior.
- Need to store or display a raw secret.
