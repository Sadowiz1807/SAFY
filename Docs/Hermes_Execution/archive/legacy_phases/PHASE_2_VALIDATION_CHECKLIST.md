# Phase 2 Validation Checklist

## Status Semantics

| Status | Meaning |
|---|---|
| DOCUMENTED | Requirement appears in canonical documentation |
| VERIFIED_DOCUMENTATION | Requirement was checked across core docs for consistency |
| IMPLEMENTED | Code/module exists for the original Phase 2 foundation |
| TESTED | Runtime behavior was executed by tests |
| NOT_YET_VERIFIED | Later refinement exists in docs but has not been verified in code/tests |
| FAIL | Conflict, broken reference, or unsafe claim remains |

Documentation verification is not runtime testing.

## Documentation Gates

| Gate | Status | Evidence |
|---|---|---|
| No duplicate canonical runtime schema in source | VERIFIED_DOCUMENTATION | `SAFY_source.md` section 7.2 delegates field detail to Data Schema |
| Current DB profile permission uses `user_query_access_mode` | VERIFIED_DOCUMENTATION | `SAFY_source.md`, `PHASE_2_DATA_SCHEMA_SPEC.md`, `PHASE_2_CONTRACTS.md` |
| Legacy permission fields are migration-only | VERIFIED_DOCUMENTATION | Source migration wording and schema constraints |
| Project tree includes Phase 2 foundation modules | VERIFIED_DOCUMENTATION | `SAFY_source.md` project structure |
| Plan has one ordered section sequence | VERIFIED_DOCUMENTATION | `PHASE_2_PLAN.md` sections 1-16 |
| Plan references only existing canonical related docs | VERIFIED_DOCUMENTATION | `PHASE_2_PLAN.md` section 16 |
| Security runtime scope includes provenance/snapshots/locks | VERIFIED_DOCUMENTATION | `PHASE_2_SECURITY_SPEC.md` section 9 |
| Audit repair state for Safy product v1.0.0 uses `audit_log` fields introduced by audit schema v2; separate queue is future-only | VERIFIED_DOCUMENTATION | `PHASE_2_SECURITY_SPEC.md` and `PHASE_2_DATA_SCHEMA_SPEC.md` |
| Runtime/audit schema version strategy is hybrid and documented | VERIFIED_DOCUMENTATION | Source, Data Schema, Plan, Security Spec, Delta Plan, Matrix |
| Matrix includes five remaining open decisions | VERIFIED_DOCUMENTATION | `PHASE_2_ARTIFACT_CONSISTENCY_MATRIX.md` |
| Final acceptance separates documentation from implementation | VERIFIED_DOCUMENTATION | `PHASE_2_FINAL_ACCEPTANCE_CHECKLIST.md` |

## Original Foundation Evidence

| Area | Status | Evidence |
|---|---|---|
| Config loader/profile/env/runtime/audit foundation | IMPLEMENTED | Historical task artifacts; reports are evidence-only |
| Profile API/UI integration foundation | IMPLEMENTED | Historical task artifacts; reports are evidence-only |
| Runtime/audit SQLite initialization foundation | IMPLEMENTED | Historical task artifacts; reports are evidence-only |

## Later Refinement Evidence

| Refinement | Status | Required Before TESTED |
|---|---|---|
| `workflow_object_provenance` table and methods | NOT_YET_VERIFIED | Implement/migrate and test CRUD/rollback decisions |
| `schema_snapshots` table and invalidation | NOT_YET_VERIFIED | Implement/migrate and test invalidation |
| `workspace_locks` table and lifecycle | NOT_YET_VERIFIED | Implement/migrate and test locking/reclaim |
| Atomic `validate_and_reserve` | NOT_YET_VERIFIED | Implement atomic reservation and concurrency tests |
| Audit repair fields/transitions | NOT_YET_VERIFIED | Implement post-execution update failure repair path |
| `user_query_access_mode` migration | NOT_YET_VERIFIED | Implement migration from legacy profile fields |
| Runtime/audit v1 -> v2 formal migration | NOT_YET_VERIFIED | Implement formal migration before release v1.0.0 |
| Development destructive rebuild guardrails | NOT_YET_VERIFIED | Implement explicit local-only rebuild behavior; never silent production rebuild |
| Canonical migration errors | NOT_YET_VERIFIED | Implement and test error branches |

## Scope Gate

- Real LLM execution: out of scope.
- Real Docker sandbox execution: out of scope.
- Real connected-database SQL execution: out of scope.
- Full SQL Guard: out of scope.
- Phase 3 dispatch: requires explicit approval.

## Evidence Semantics

- Documentation-only checks use `VERIFIED_DOCUMENTATION`.
- Runtime/code test evidence requires `TESTED`.
- Report summaries alone cannot produce `TESTED`.
