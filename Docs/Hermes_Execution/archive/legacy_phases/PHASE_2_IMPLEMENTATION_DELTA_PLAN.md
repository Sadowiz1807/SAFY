# Phase 2 Implementation Delta Plan

## 1. Purpose

This is a task-contract-generation-ready planning document.
It is not dispatch-ready and does not dispatch implementation.

Current status:
- Original Phase 2 implementation foundation: `COMPLETED` by historical evidence.
- Final Phase 2 refinement implementation: `NOT_VERIFIED`.
- Phase 3 dispatch: requires explicit user approval.

## 2. Schema Version Strategy

Profile JSON `schema_version` is independent from `runtime_schema_version` and `audit_schema_version`. Profile JSON remains schema version `1` unless a separate profile-schema migration is approved.

| Component | Historical Foundation | Final Refined Target | Planning/Development Policy | Release v1.0.0 Policy |
|---|---:|---:|---|---|
| Runtime DB | v1 | v2 | Local destructive rebuild allowed with explicit operator/developer action | Formal v1 -> v2 migration required |
| Audit DB | v1 | v2 | Local destructive rebuild allowed with explicit operator/developer action | Formal v1 -> v2 migration required |

Rules:
- Destructive rebuild is allowed only for current planning/development local files.
- Destructive rebuild must not be the only production mechanism.
- Startup must not silently delete or rebuild runtime/audit DB files.
- Formal migrations must be available before release v1.0.0.
- Migration/rebuild evidence must be recorded before any implementation claim changes from `NOT_VERIFIED`.

## 3. Allowed Paths

Documentation-only planning currently allows references to these future implementation areas:
- `DataStore/config_loader.py`
- `DataStore/profile_store.py`
- `DataStore/env_writer.py`
- `DataStore/env_secret_resolver.py`
- `State/runtime_db.py`
- `State/high_risk_code_state.py`
- `Audit/audit_store.py`
- `Audit/audit_logger.py`
- `Logging/redact.py`
- `Apps/Api/`
- `Apps/Web/`
- `Tests/`

This plan does not modify those paths.

## 4. Must Not Modify During Delta Implementation

Future implementation tasks must not:
- weaken agent connected-database read-only policy;
- store raw secrets in JSON, API responses, audit logs, operational logs, or frontend state;
- use SQLite as fallback validation for PostgreSQL/MySQL SQL;
- treat `manual_write_enabled` as v1 execution authority;
- silently choose Phase 2 open decisions without user approval;
- start Phase 3 implementation without explicit dispatch approval;
- use reports as source-of-truth for schema or contracts.

## 5. Dependency Order

| Order | Task ID | Depends On | Purpose | Affected Areas | Status |
|---:|---|---|---|---|---|
| 1 | P2-DELTA-SCHEMA-VERSION | user-approved hybrid strategy | Introduce runtime/audit v2 target and migration/rebuild guardrails | `State/runtime_db.py`, `Audit/audit_store.py`, tests | NOT_VERIFIED |
| 2 | P2-DELTA-RUNTIME-PROVENANCE | P2-DELTA-SCHEMA-VERSION | Add `workflow_object_provenance` table and RuntimeDB methods | `State/runtime_db.py`, workflow integration, tests | NOT_VERIFIED |
| 3 | P2-DELTA-SCHEMA-SNAPSHOTS | P2-DELTA-SCHEMA-VERSION | Add `schema_snapshots` table and invalidation methods | `State/runtime_db.py`, Text-to-SQL context, tests | NOT_VERIFIED |
| 4 | P2-DELTA-WORKSPACE-LOCKS | P2-DELTA-SCHEMA-VERSION | Add `workspace_locks` table and lock lifecycle | `State/runtime_db.py`, workspace cleanup/mutation/query/recovery tests | NOT_VERIFIED |
| 5 | P2-DELTA-CONFIRMATION-ATOMIC-CORE | None | Implement mandatory atomic `validate_and_reserve`, consume, release/cancel behavior for selected local adapter | `State/high_risk_code_state.py`, API flow, proposed tests | NOT_VERIFIED |
| 6 | P2-DELTA-CONFIRMATION-PERSISTENCE-ADAPTER | blocked_if confirmation persistence backend remains undecided for target deployment | Optional SQLite/shared persistence adapter preserving the atomic lifecycle | `State/high_risk_code_state.py`, runtime persistence adapter, proposed tests | NOT_VERIFIED |
| 7 | P2-DELTA-AUDIT-REPAIR | P2-DELTA-SCHEMA-VERSION | Add audit repair fields/transitions and retry behavior | `Audit/audit_store.py`, `Audit/audit_logger.py`, proposed tests | NOT_VERIFIED |
| 8 | P2-DELTA-PROFILE-MIGRATION | schema/profile fixture readiness | Migrate legacy profile fields to `user_query_access_mode` | `DataStore/profile_store.py`, profile fixtures, API tests | NOT_VERIFIED |
| 9 | P2-DELTA-MIGRATION-ERRORS | P2-DELTA-SCHEMA-VERSION | Implement canonical migration/rebuild error behavior | runtime/audit init, error mapping, tests | NOT_VERIFIED |
| 10 | P2-DELTA-API-UI-EVIDENCE | prior delta tasks | Prove masked API/UI responses and right-sidebar behavior stay consistent | `Apps/Api/`, `Apps/Web/`, integration tests | NOT_VERIFIED |

## 6. Task Acceptance Criteria

### P2-DELTA-SCHEMA-VERSION
- Runtime DB reports required version `2` for final refined schema.
- Audit DB reports required version `2` for final refined schema.
- v1 local DB can be handled through explicit development rebuild or formal migration path.
- Production path refuses silent destructive rebuild.
- Errors map to `MIGRATION_REQUIRED`, `SCHEMA_VERSION_UNSUPPORTED`, `MIGRATION_FAILED`, `MIGRATION_ROLLBACK_FAILED`, or `DATABASE_INITIALIZATION_FAILED`.

### P2-DELTA-RUNTIME-PROVENANCE
- `workflow_object_provenance` exists in runtime v2.
- Methods support create/read/update/verify lifecycle.
- Rollback/drop checks provenance before acting.
- Metadata is redacted and size-limited.

### P2-DELTA-SCHEMA-SNAPSHOTS
- `schema_snapshots` exists in runtime v2.
- Snapshot create/read/invalidate methods exist.
- Mutation invalidates target-matching snapshots.
- Snapshot payload contains no raw secrets.

### P2-DELTA-WORKSPACE-LOCKS
- `workspace_locks` exists in runtime v2.
- Acquisition is atomic for `(workspace_id, lock_type)`.
- Expiry/release/force-release behavior is deterministic.
- Cleanup, query, mutation, and recovery respect locks.

### P2-DELTA-CONFIRMATION-ATOMIC-CORE
- High-risk code is backend-generated and visible only as intended.
- `validate_and_reserve` is atomic for every backend, including in-memory single-process.
- This task is mandatory and unblocked by the persistence-backend decision.
- Challenge is bound to check_id + SQL hash + target + expiry.
- Replay, expiry, mismatch, and double reservation are blocked.
- Success marks consumed; failure before side effect releases reservation or invalidates by policy.

### P2-DELTA-CONFIRMATION-PERSISTENCE-ADAPTER
- `blocked_if`: confirmation persistence backend remains undecided for the target deployment mode.
- SQLite/shared persistence adapter is implemented only after the backend decision where applicable.
- Adapter preserves the same atomic lifecycle as `P2-DELTA-CONFIRMATION-ATOMIC-CORE`.

### P2-DELTA-AUDIT-REPAIR
- High-risk pre-write audit failure blocks execution.
- Post-execution update failure marks repair required.
- Repair fields live in `audit_log` for v2 refined target.
- Retry state transitions are deterministic and redacted.

### P2-DELTA-PROFILE-MIGRATION
- Legacy direct-array profile JSON is migrated to the wrapped `schema_version` + `profiles` container.
- Migration backs up legacy profile files, preserves profiles, is idempotent, returns controlled corrupt-input errors, and introduces no raw secrets.
- Current field is `user_query_access_mode`.
- Legacy permission fields are accepted only through migration fixtures where explicitly allowed.
- `manual_write_enabled` does not block user query execution in v1.
- Profile JSON never stores raw secrets.

### P2-DELTA-MIGRATION-ERRORS
- Version lower than required returns `MIGRATION_REQUIRED`.
- Version higher than supported returns `SCHEMA_VERSION_UNSUPPORTED`.
- Failed migration returns `MIGRATION_FAILED`.
- Failed rollback returns `MIGRATION_ROLLBACK_FAILED`.
- Unsafe initialization returns `DATABASE_INITIALIZATION_FAILED`.

### P2-DELTA-API-UI-EVIDENCE
- API responses mask secrets.
- Frontend never receives raw secrets.
- Right execution sidebar reflects selected credential permission and confirmation state.
- Agent connected DB path remains read-only.

## 7. Test Commands

Exact commands must be adapted to the final repository test runner. The following are proposed test paths. They may be created during implementation or replaced by equivalent tests. They do not imply the files already exist. Minimum expected commands:

```bash
python -m pytest Tests/phase2/test_runtime_schema_v2.py
python -m pytest Tests/phase2/test_audit_schema_v2.py
python -m pytest Tests/phase2/test_profile_migration.py
python -m pytest Tests/phase2/test_high_risk_confirmation_atomicity.py
python -m pytest Tests/phase2/test_audit_repair.py
python -m pytest Tests/phase2/test_secret_redaction.py
python -m pytest Tests/phase2/test_api_ui_profile_contracts.py
```

If no test runner exists yet, implementation must create tests or equivalent verification scripts before changing any `NOT_VERIFIED` status.

## 8. Evidence Artifacts

Future implementation must produce direct evidence, not report-only claims:
- migration/rebuild logs for runtime v1 -> v2 and audit v1 -> v2;
- test output for every command in section 7 or equivalent;
- before/after schema introspection for runtime/audit DB;
- profile migration fixture results;
- confirmation race/replay test evidence;
- audit fail-closed and repair-state test evidence;
- secret redaction test evidence.

Suggested evidence file after implementation:
- `Docs/Hermes_Execution/PHASE_2_IMPLEMENTATION_DELTA_EVIDENCE.md`

This evidence file must be created only after implementation/testing, not during this documentation repair.

## 9. Rollback Strategy

Development rollback:
- stop Safy processes;
- back up local `Data/safy_runtime.db` and `Data/safy_audit.db` if evidence is needed;
- delete/recreate local DB files only when explicitly authorized for development;
- restore profile JSON from backup if migration tests fail.

Production/release rollback:
- destructive rebuild is not allowed as the only rollback;
- migration must be transactional where SQLite supports it;
- failed migration must return `MIGRATION_FAILED`;
- failed rollback must return `MIGRATION_ROLLBACK_FAILED`;
- high-risk Manual SQL remains blocked until audit DB is safe.

## 10. Definition of Done

The delta is done only when:
- runtime and audit schema v2 are implemented or formally migrated;
- v1 -> v2 formal migration is available before release v1.0.0;
- development destructive rebuild behavior is explicit and never silent in production;
- every delta task has passing direct tests or equivalent verification evidence;
- no core artifact relies on reports as source-of-truth;
- `PHASE_2_VALIDATION_CHECKLIST.md` can move relevant rows from `NOT_YET_VERIFIED` to `IMPLEMENTED`/`TESTED` using direct evidence;
- `PHASE_2_FINAL_ACCEPTANCE_CHECKLIST.md` can be updated without overstating implementation.

## 11. Current Handoff

Do not dispatch these tasks automatically. Carry this plan into Phase 3 prerequisites or a separate user-approved implementation/hardening task.
