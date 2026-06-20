# Phase 3 Plan

## 1. Purpose

Create a controlled Phase 3 plan for Safy that can be executed by a single main agent without real sub-agent dispatch and without assuming unverified Phase 2 final refinements.

## 2. Objective

Phase 3 prepares implementation task contracts, security gates, and validation evidence boundaries for the next work package. Because no Phase 3 artifacts existed at the start of this run, the first Phase 3 objective is coherent planning and readiness classification.

## 3. Source And Authority Model

| Domain | Authority |
| --- | --- |
| Product intent, architecture, module ownership, policy boundaries | `SAFY_source.md` |
| Phase 2 interface/lifecycle/error/atomicity/concurrency contracts | `PHASE_2_CONTRACTS.md` |
| Phase 2 fields/tables/versions/migrations | `PHASE_2_DATA_SCHEMA_SPEC.md` |
| Phase 2 security invariants and fail-open/fail-closed rules | `PHASE_2_SECURITY_SPEC.md` |
| Phase 3 scope, sequence, gates, dependencies, handoff | `PHASE_3_PLAN.md` |
| Phase 3 task contracts | `PHASE_3_TASKS.yaml` |
| Phase 3 interface obligations | `PHASE_3_CONTRACTS.md` |
| Phase 3 safety gates | `PHASE_3_SECURITY_SPEC.md` |
| Phase 3 evidence checks | `PHASE_3_VALIDATION_CHECKLIST.md` |
| Historical evidence only | Phase 2 task/gate/report artifacts |

Reports do not override specs or contracts.

## 4. In Scope

- Phase 3 documentation and task-contract generation.
- Phase 3 dependency classification against Phase 2 final refinements.
- Phase 3 safety and validation gates.
- Documentation-only execution logging and review passes.
- Future-ready task contracts for implementation/hardening work.

## 5. Out Of Scope

- Real sub-agent dispatch.
- Real connected-database execution.
- Destructive database operation.
- Real external provider call.
- Code implementation that depends on Phase 2 final refinements still marked `NOT_VERIFIED`.
- Phase 3 completion claims without direct implementation and test evidence.

## 6. Inputs And Dependencies

Inputs:

- `SAFY_source.md`.
- Phase 2 canonical docs listed in `PHASE_3_RESTATEMENT.md`. Historical reports, if retained, are evidence-only and not required inputs listed in `PHASE_3_RESTATEMENT.md`.
- Current Phase 3 prompt and user approval to run single-agent planning.

Dependencies:

- Phase 2 documentation: `PASS_WITH_OPEN_DECISIONS`.
- Original Phase 2 implementation foundation: `COMPLETED_BY_HISTORICAL_EVIDENCE`.
- Final Phase 2 refinement implementation: `NOT_VERIFIED`.
- Implementation Delta Plan: `READY_FOR_TASK_CONTRACT_GENERATION`.
- Phase 3 dispatch: explicit user approval required.

## 7. Deliverables

Core deliverables:
- `PHASE_3_RESTATEMENT.md`.
- `PHASE_3_FRAMEWORK_COMPARISON.md`.
- `PHASE_3_PLAN.md`.
- `PHASE_3_TASKS.yaml`.
- `PHASE_3_CONTRACTS.md`.
- `PHASE_3_SECURITY_SPEC.md`.
- `PHASE_3_VALIDATION_CHECKLIST.md`.

Reports:
- Generated under `Docs/Hermes_Execution/report/` when needed.
- Reports, review logs, execution logs, gate reports, and final reports are evidence-only.
- They must not override source, plan, contract, schema, security spec, validation checklist, or task board.

## 8. Phase 2 Dependency Boundary

Phase 3 must not assume these Phase 2 final refinements are implemented:

- Runtime/audit schema v2.
- `workflow_object_provenance`.
- `schema_snapshots`.
- `workspace_locks`.
- Atomic `validate_and_reserve`.
- Audit repair fields/transitions.
- Profile container migration.
- `user_query_access_mode` migration.
- Canonical migration error behavior.

Any task requiring them is `BLOCKED_BY_PHASE_2_DELTA` unless converted into a Phase 2 prerequisite/hardening task.

## 9. Execution Sequence

1. Restate Phase 3.
2. Compare Phase 3 against Safy framework.
3. Improve/create Phase 3 artifacts.
4. Execute only `READY_TO_IMPLEMENT` tasks.
5. Simulate read-only review pass 1.
6. Fix P0/P1/P2 issues if safe.
7. Simulate read-only review pass 2.
8. Write final report only if pass 2 has no P0/P1.

## 10. Task Contracts

Task contracts are defined in `PHASE_3_TASKS.yaml`. Current task classification:

| Task ID | Classification | Summary |
| --- | --- | --- |
| `P3-DOCS-PLAN-001` | `READY_TO_IMPLEMENT` | Create Phase 3 plan/contracts/tasks/checklist/security docs. |
| `P3-DELTA-PREREQ-001` | `BLOCKED_BY_PHASE_2_DELTA` | Implement Phase 2 delta prerequisites needed before runtime Phase 3 work. |
| `P3-RUNTIME-ORCHESTRATION-001` | `BLOCKED_BY_PHASE_2_DELTA` | Runtime orchestration that needs provenance/snapshots/locks/schema v2. |
| `P3-CONNECTED-DB-SAFETY-001` | `BLOCKED_BY_PHASE_2_DELTA` | Connected DB safety hardening requiring audit pre-write and user query authority migration evidence. |
| `P3-PRODUCTION-DECISIONS-001` | `BLOCKED_BY_USER_DECISION` | Resolve deployment and retention decisions. |
| `P3-VALIDATION-HARNESS-001` | `DEFERRED` | Build broad validation harness after prerequisites are verified. |

## 11. Safety And Security Gates

- Agent connected DB remains strict read-only.
- User query box requires selected credential permission, safety check, explicit user confirmation, high-risk challenge when required, and audit pre-write.
- No raw secrets in JSON, API responses, logs, frontend state, or audit output.
- High-risk audit pre-write failure is fail-closed.
- PostgreSQL/MySQL SQL must not be validated by SQLite fallback.
- Reports are evidence only and cannot become authority.

## 12. Validation Plan

Validation is defined in `PHASE_3_VALIDATION_CHECKLIST.md`. Documentation validation checks that artifacts exist, task statuses are honest, Phase 2 blockers are respected, and no implementation/test evidence is overclaimed.

## 13. Open Decisions

- Confirmation persistence backend.
- Runtime/audit generated artifact policy.
- Confirmation TTL and attempt limit.
- Windows locking implementation.
- Audit retention duration.
- Explicit Phase 3 implementation dispatch approval.
- Explicit approval for any real connected-database execution.
- Explicit approval for any destructive database operation.

## 14. Blockers

- Phase 2 final refinement implementation remains `NOT_VERIFIED`.
- Phase 3 implementation tasks that need Phase 2 delta outputs are blocked.
- User decisions remain open for production/security behavior.

## 15. Handoff

A future executor must start from this plan, read all referenced authority files directly, and execute only tasks with `READY_TO_IMPLEMENT` status. Blocked tasks must not be implemented until their blocker is resolved and evidence is recorded.

## 16. Final Status Vocabulary

Phase 3 planning: `PASS`, `PASS_WITH_OPEN_DECISIONS`, `FAIL`.

Phase 3 implementation: `NOT_STARTED`, `PARTIAL`, `IMPLEMENTED_NOT_TESTED`, `TESTED`, `BLOCKED`.

Phase 2 dependency usage: `RESPECTED`, `VIOLATED`.

Sub-agents: `NOT_USED`.

Review pass: `PASS`, `PASS_WITH_FIXES`, `PASS_WITH_RESIDUAL_P2`, `FAIL`.

Final recommendation: `CONTINUE`, `STOP_FOR_USER_DECISION`, `READY_FOR_NEXT_PHASE`.


## Execution Readiness Boundary

Phase 3 execution is blocked until Phase 2 delta implementation is verified with direct evidence and explicit user approval. Phase 3 planning artifacts may be synchronized now, but they must not be treated as permission to implement or dispatch Phase 3 tasks.
