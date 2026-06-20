# Phase 2 Plan - Runtime, Profiles, Secrets, and Audit Base

## 1. Purpose

Phase 2 establishes the runtime, profile, secret, audit, redaction, configuration, and persistence foundation required by later Safy phases.

It separates:
- the original implementation foundation,
- the finalized documentation contracts,
- and the implementation delta that remains unverified.

## 2. Phase Objective

Provide stable contracts and foundations for:
- non-secret configuration loading,
- JSON profile persistence,
- `.env` secret handling,
- runtime SQLite state,
- audit SQLite evidence,
- high-risk confirmation state,
- profile API/UI integration,
- provenance, schema snapshots, and workspace coordination.

## 3. Source and Decision Ownership

Authority map:

| Decision Type | Canonical Owner |
|---|---|
| Product and architecture policy | `SAFY_source.md` |
| Interface behavior | `PHASE_2_CONTRACTS.md` |
| Field/table schema | `PHASE_2_DATA_SCHEMA_SPEC.md` |
| Threat and security constraints | `PHASE_2_SECURITY_SPEC.md` |
| Phase scope, order, and gates | `PHASE_2_PLAN.md` |
| Evidence state | `PHASE_2_VALIDATION_CHECKLIST.md` |
| Historical implementation record | `PHASE_2_TASKS.yaml`; retained reports are evidence only |

Conflict rule:
- A report cannot override a core specification.
- Historical task/gate artifacts cannot prove later refinements were implemented.
- Addenda are historical notes only; they must not override a conflicting earlier section.

## 4. In Scope

- Config loading.
- Profile JSON stores.
- Atomic/staged JSON writes.
- `.env` secret writes.
- Secret resolution.
- Runtime SQLite foundation.
- Audit SQLite foundation.
- Redaction.
- Profile API/UI integration.
- High-risk confirmation state contract.
- `workflow_object_provenance` contract.
- `schema_snapshots` contract.
- `workspace_locks` contract.
- Audit repair state contract.
- Migration/error contracts.
- Documentation validation.

## 5. Out of Scope

- Real LLM provider execution.
- Real agent workflow.
- Real Docker sandbox execution.
- Real connected-database SQL execution.
- Full SQL Guard.
- Real create_database/text_to_sql workflow.
- Production authentication.
- Encryption at rest.
- Phase 3 dispatch.
- Claiming untested refinements as implemented.

## 6. Inputs and Dependencies

- `SAFY_source.md`.
- Phase 1 UI/API contracts.
- P1.5 UI-backend mock integration.
- `PHASE_2_CONTRACTS.md`.
- `PHASE_2_DATA_SCHEMA_SPEC.md`.
- `PHASE_2_SECURITY_SPEC.md`.

## 7. Deliverables

Core deliverables:
- `PHASE_2_PLAN.md`.
- `PHASE_2_CONTRACTS.md`.
- `PHASE_2_DATA_SCHEMA_SPEC.md`.
- `PHASE_2_SECURITY_SPEC.md`.
- `PHASE_2_VALIDATION_CHECKLIST.md`.
- `PHASE_2_TASKS.yaml`.
- `PHASE_2_ARTIFACT_CONSISTENCY_MATRIX.md`.
- `PHASE_2_FINAL_ACCEPTANCE_CHECKLIST.md`.

Historical reports:
- Reports, gate reports, and review logs are evidence only.
- Historical reports, if retained, live under `Docs/Hermes_Execution/report/`.

Removed or temporary reports are not deliverables and must not be used as decision authority.

## 8. Original Implementation Foundation

The original Phase 2 implementation foundation created or recorded:
- Config loader.
- Profile stores.
- Env writer.
- Secret resolver.
- Runtime DB base tables.
- Audit DB base table.
- Redactor.
- Initial confirmation state.
- Profile API/UI integration.

This implementation is historical evidence. It does not prove later documentation refinements are implemented.

## 9. Finalized Documentation Model

Profiles:
- JSON profile containers use `schema_version` plus `profiles`.
- Database profiles use `user_query_access_mode`.
- Secrets are stored as env references only.

Runtime:
- Historical foundation schema version: `1`.
- Final refined target schema version: `2`.
- Planning/development may destructively rebuild local runtime DB files.
- Release v1.0.0 requires formal runtime v1 -> v2 migration; destructive rebuild cannot be production-only.
- `schema_version`.
- `chat_runtime`.
- `sandbox_workspaces`.
- `workflow_object_provenance`.
- `schema_snapshots`.
- `workspace_locks`.

Audit:
- Historical foundation schema version: `1`.
- Final refined target schema version: `2`.
- Planning/development may destructively rebuild local audit DB files.
- Release v1.0.0 requires formal audit v1 -> v2 migration; destructive rebuild cannot be production-only.
- `statement_hash`.
- `redacted_sql`.
- `raw_sql_stored` defaults false.
- High-risk pre-write fails closed.
- For Safy product v1.0.0, audit repair state is stored in `audit_log` fields introduced by audit schema v2.

Confirmation:
- Atomic `validate_and_reserve`.
- Reservation lifecycle.
- Single-use challenge consumption.

## 10. Integration Flows

### Profile flow

```txt
UI
-> API/Gateway
-> ProfileSaveCoordinator
-> EnvWriter + ProfileStore
-> masked response
```

### Runtime flow

```txt
chat/session event
-> RuntimeDB
-> chat_runtime / sandbox_workspaces
```

### Provenance flow

```txt
DDL result
-> verify objects
-> workflow_object_provenance
-> safe rollback/drop decision
```

### Snapshot flow

```txt
schema read
-> schema_snapshots

schema mutation
-> invalidate matching snapshot
```

### Workspace lock flow

```txt
query/mutation/cleanup/recovery
-> acquire lock
-> execute action
-> renew if required
-> release lock
```

### Confirmation flow

```txt
create challenge
-> validate_and_reserve atomically
-> perform authorized operation
-> mark_consumed

failure before side effect
-> release_reservation
```

### Audit flow

```txt
pre-execution audit
-> success required for high-risk
-> execution

post-execution audit update failure
-> mark audit_repair_required
-> retry through audit_log repair state
```

## 11. Failure Handling

| Failure | Required Behavior |
|---|---|
| Config parse/validation | Controlled config error |
| Profile/env write | Stage, validate, commit, and roll back where possible |
| Missing secret | `MISSING_ENV_SECRET` |
| Runtime schema older | `MIGRATION_REQUIRED` |
| Runtime schema newer | `SCHEMA_VERSION_UNSUPPORTED` |
| Development rebuild allowed | Local runtime/audit DB destructive rebuild only during planning/development with explicit operator/developer action |
| Production migration required | Formal runtime/audit v1 -> v2 migration before release v1.0.0 |
| Migration failure | `MIGRATION_FAILED` |
| Rollback failure | `MIGRATION_ROLLBACK_FAILED` |
| High-risk pre-audit failure | `AUDIT_WRITE_FAILED` and no execution |
| Confirmation mismatch/replay/expiry | Block operation |

## 12. Validation Gates

Gate 0: task contract completeness.

Documentation gate:
- No duplicate canonical definition.
- No stale reference.
- No contradictory enum/field/policy.

Security gate:
- No raw secrets in JSON/API/log-safe output.
- Audit defaults safe.
- High-risk pre-write fail-closed.

Evidence gate:
- Documentation verification is not runtime testing.
- Later refinements remain `NOT_VERIFIED` until code and tests prove otherwise.

Scope gate:
- No Phase 3 dispatch.

## 13. Open Decisions

### 13.1. Confirmation persistence backend

- Options: in-memory single-worker MVP; runtime SQLite-backed state; external shared store.
- Recommendation: in-memory MVP for local single-worker; SQLite before multi-worker.
- Trade-off: speed and simplicity versus replay/reservation safety across workers.
- Implementation impact: changes `HighRiskCodeState` storage and reservation tests.
- Blocking scope: does not block Phase 3 planning; blocks production/multi-worker execution.
- Artifact policy không reopen migration/rebuild strategy

### 13.2. Runtime/audit DB artifact policy

- Options: generated local artifacts; committed fixtures only; operator-managed files.
- Recommendation: generate runtime/audit DB locally and commit schema/migration code only.
- Trade-off: clean repository versus reproducible local state.
- Implementation impact: startup initialization, migrations, and test fixtures.
- Blocking scope: does not block Phase 3 planning; must be decided before packaging/release.

### 13.3. Confirmation TTL and attempt limit

- Options: short strict TTL with low attempts; configurable local policy; longer development TTL.
- Recommendation: short default TTL and low attempt count, configurable by policy.
- Trade-off: usability versus brute-force resistance.
- Implementation impact: challenge validation, errors, UI timer, tests.
- Blocking scope: does not block Phase 3 planning; blocks production confirmation security.

### 13.4. Windows locking implementation

- Options: process-local lock; cross-platform file lock library; SQLite coordination.
- Recommendation: process-local only for MVP; cross-platform lock or SQLite coordination before multi-process.
- Trade-off: portability and correctness versus dependency/complexity.
- Implementation impact: profile/env writer concurrency behavior and tests.
- Blocking scope: does not block Phase 3 planning; blocks multi-process execution claims.

### 13.5. Audit retention duration

- Options: no automatic retention in MVP; configurable retention; legal/compliance policy.
- Recommendation: no destructive retention until user policy is chosen.
- Trade-off: privacy/storage reduction versus audit evidence preservation.
- Implementation impact: audit cleanup jobs, retention metadata, UI/admin policy.
- Blocking scope: does not block Phase 3 planning; blocks production retention policy.

## 14. Implementation Delta

Implementation delta planning owner: PHASE_2_IMPLEMENTATION_DELTA_PLAN.md

The following refinements are not yet verified in code:
- runtime/audit schema version transition from v1 foundation to v2 refined target.
- `workflow_object_provenance` table and methods.
- `schema_snapshots` table and invalidation.
- `workspace_locks` table and lock lifecycle.
- Atomic `validate_and_reserve`.
- Audit repair fields and transitions.
- `user_query_access_mode` migration.
- Canonical migration error behavior.

This section prevents Phase 3 from assuming documentation equals implementation.

## 15. Handoff to Phase 3

Phase 3 planning may begin after:
- documentation consistency passes,
- open decisions are acknowledged,
- implementation delta is carried into Phase 3 prerequisites or a separate hardening task.

Phase 3 implementation must not silently depend on unverified Phase 2 refinements.

Phase 3 dispatch requires explicit user approval.

## 16. Related Documents

Core related documents:
- `SAFY_source.md`.
- `PHASE_2_CONTRACTS.md`.
- `PHASE_2_DATA_SCHEMA_SPEC.md`.
- `PHASE_2_SECURITY_SPEC.md`.
- `PHASE_2_VALIDATION_CHECKLIST.md`.
- `PHASE_2_TASKS.yaml`.
- `PHASE_2_ARTIFACT_CONSISTENCY_MATRIX.md`.
- `PHASE_2_FINAL_ACCEPTANCE_CHECKLIST.md`.

Historical reports:
- Reports, if retained, live under `Docs/Hermes_Execution/report/` and are not required inputs.


## Runtime/Audit Artifact Policy

This decision controls whether generated runtime/audit DB files or fixtures are committed, local-only, or operator-managed. It does not reopen the approved runtime/audit v1 -> v2 migration and development rebuild strategy.


## Open-decision execution boundary

`PASS_WITH_OPEN_DECISIONS` means documentation is synchronized enough to plan the next phase, but unresolved product/security choices and unverified implementation refinements remain. It is not permission to execute Phase 3 or mark Phase 2 delta implementation as verified.
