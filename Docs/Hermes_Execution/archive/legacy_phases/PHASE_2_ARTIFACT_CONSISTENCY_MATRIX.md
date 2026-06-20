# Phase 2 Artifact Consistency Matrix

## 1. Status Model

Documentation status values:
- `PASS`
- `OPEN_DECISION`
- `FAIL`

Implementation evidence values:
- `TESTED`
- `IMPLEMENTED_NOT_TESTED`
- `NOT_VERIFIED`
- `NOT_APPLICABLE`

## 2. Matrix

| Concept | Canonical owner | Supporting artifacts | Conflicting occurrence scan | Documentation status | Implementation evidence | Notes |
|---|---|---|---|---|---|---|
| Authority hierarchy | `PHASE_2_PLAN.md`; `SAFY_source.md` | Contracts, schema, security, reports | No retained report/task may override core specs; reports are evidence only. | PASS | NOT_APPLICABLE | Reports/tasks are evidence only and cannot override specs. |
| Agent connected-DB read-only authority | `SAFY_source.md`; `PHASE_2_SECURITY_SPEC.md` | Contracts, plan | No current row may grant agent connected-DB write authority. | PASS | NOT_VERIFIED | Implementation not re-tested in this documentation run. |
| User query authority | `SAFY_source.md`; `PHASE_2_SECURITY_SPEC.md` | Contracts, plan | No current row may treat `manual_write_enabled` as the v1 user-query execution gate. | PASS | NOT_VERIFIED | Permission + safety + confirmation + audit pre-write. |
| `manual_write_enabled` role | `SAFY_source.md`; `PHASE_2_DATA_SCHEMA_SPEC.md` | Plan, validation | No current profile schema may require `manual_write_enabled` as execution authority. | PASS | NOT_APPLICABLE | Legacy/migration/UI/future-policy metadata only. |
| Profile JSON schema version | `PHASE_2_DATA_SCHEMA_SPEC.md` | Source, plan, delta | No current wording may conflate profile JSON schema v1 with runtime/audit schema v1/v2. | PASS | NOT_VERIFIED | Independent domain; remains v1 absent separate profile-schema migration. |
| Runtime DB schema version | `PHASE_2_DATA_SCHEMA_SPEC.md` | Source, plan, security, delta | No current wording may treat historical runtime v1 as the final refined target. | PASS | NOT_VERIFIED | Historical v1; final refined target v2; hybrid policy. |
| Audit DB schema version | `PHASE_2_DATA_SCHEMA_SPEC.md` | Source, plan, security, delta | No current wording may treat historical audit v1 as the final refined target. | PASS | NOT_VERIFIED | Historical v1; final refined target v2; hybrid policy. |
| Audit repair location | `PHASE_2_DATA_SCHEMA_SPEC.md`; `PHASE_2_SECURITY_SPEC.md` | Plan, contracts, validation | No standalone “audit repair v2” or “v1 audit repair state” wording may remain as current authority. | PASS | NOT_VERIFIED | For Safy product v1.0.0, repair state uses `audit_log` fields introduced by audit schema v2. |
| High-risk confirmation lifecycle | `PHASE_2_CONTRACTS.md`; `PHASE_2_SECURITY_SPEC.md` | Plan, delta | No current flow may use non-atomic validate → execute → consume as the main authorization flow. | PASS | NOT_VERIFIED | create -> atomic reserve -> execute -> consumed. |
| Confirmation persistence backend | `PHASE_2_PLAN.md` open decisions | Delta | No current artifact may silently choose SQLite/shared/in-memory persistence for all deployments. | OPEN_DECISION | NOT_VERIFIED | Backend remains open; atomicity is still mandatory. |
| Runtime/audit artifact policy | `PHASE_2_PLAN.md` open decisions | Delta | No current artifact may treat artifact policy as reopening the approved v1 -> v2 migration/rebuild strategy. | OPEN_DECISION | NOT_APPLICABLE | Controls generated DB files/fixtures only; does not reopen v1 -> v2 migration strategy. |
| Confirmation TTL and attempt limit | `PHASE_2_PLAN.md` open decisions | Security, delta | No production confirmation flow may be accepted without explicit TTL/attempt policy. | OPEN_DECISION | NOT_APPLICABLE | Values remain product/security policy decisions. |
| Windows locking implementation | `PHASE_2_PLAN.md` open decisions | Security, contracts | No multi-process/multi-worker execution claim may rely only on process-local locking. | OPEN_DECISION | NOT_APPLICABLE | Windows/cross-platform locking strategy remains open. |
| Audit retention duration | `PHASE_2_PLAN.md` open decisions | Security, audit docs | No destructive audit cleanup may run without explicit retention policy. | OPEN_DECISION | NOT_APPLICABLE | Retention duration remains open. |
| Historical task dispatchability | `PHASE_2_TASKS.yaml` | Gate/final reports | No completed historical task may remain currently dispatchable. | PASS | NOT_APPLICABLE | Historical task board only; do not dispatch. |
| Report evidence boundary | Historical reports | Final reports | No report row may be used to prove final schema v2 refinements. | PASS | NOT_APPLICABLE | Reports are evidence-only; original implementation foundation status is reported separately as `COMPLETED_BY_HISTORICAL_EVIDENCE`. |
| Report authority | `PHASE_2_PLAN.md` section 3 | Final reports, Gate Report, Acceptance Checklist | No report may self-authorize as architecture/specification owner. | PASS | NOT_APPLICABLE | Final/review reports are summary/evidence only; they do not override core artifacts. |
| Project tree paths | `SAFY_source.md` | Delta | No implementation task may use stale or non-canonical module paths. | PASS | NOT_APPLICABLE | Existing/target/conceptual statuses are distinguished. |
| Proposed test paths | `PHASE_2_IMPLEMENTATION_DELTA_PLAN.md` | Checklist | No proposed test path may be described as already existing unless verified. | PASS | NOT_APPLICABLE | Proposed `Tests/phase2/` paths or equivalent. |
| Phase 3 dispatch | `PHASE_2_PLAN.md`; acceptance checklist | Delta | No current artifact may state Phase 3 was dispatched. | PASS | NOT_APPLICABLE | NOT_DISPATCHED unless explicitly approved. |

## 3. Remaining Open Decisions

1. Confirmation persistence backend.
2. Runtime/audit DB artifact policy. This decision controls whether generated DB files or fixtures are committed, local-only, or operator-managed. It does not reopen the approved runtime/audit v1 -> v2 migration/rebuild strategy.
3. Confirmation TTL and attempt limit.
4. Windows locking implementation.
5. Audit retention duration.
