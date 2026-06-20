# Phase 3 Framework Comparison

## Initial Phase 3 Artifact State

Current Phase 3 files before this run:

- `PHASE_3_PLAN.md`: `PHASE_3_PLAN_NOT_FOUND`.
- `PHASE_3_TASKS.yaml`: `NOT_FOUND`.
- `PHASE_3_CONTRACTS.md`: `NOT_FOUND`.
- `PHASE_3_SECURITY_SPEC.md`: `NOT_FOUND`.
- `PHASE_3_VALIDATION_CHECKLIST.md`: `NOT_FOUND`.

Because no current Phase 3 plan existed, Phase 3 must be created from the Safy framework and Phase 2 boundaries before any implementation task is executed.

## Safy Product Framework

Current Phase 3 state:
No Phase 3 plan existed. The only current guidance is the Safy source and Phase 2 documentation.

Expected state:
Phase 3 must preserve: LLM suggests, Safy verifies, sandbox tests, policy decides, audit records, and user explicitly authorizes risky manual actions.

Gap:
No Phase 3-specific plan, tasks, contracts, security spec, or validation checklist existed.

Risk:
Without Phase 3 artifacts, an executor could implement code directly and bypass verification, sandbox, policy, audit, or explicit user authorization boundaries.

Required improvement:
Create Phase 3 artifacts before implementation. Define task contracts and mark tasks blocked when they require Phase 2 final refinements that remain `NOT_VERIFIED`.

Blocking status:
`BLOCKING_FOR_IMPLEMENTATION`; not blocking for documentation/task-contract creation.

## Authority Framework

Current Phase 3 state:
No Phase 3 authority model existed.

Expected state:
`SAFY_source.md` owns product intent, architecture, policy boundaries, and module ownership. Contracts own interfaces/lifecycles/errors/atomicity/concurrency. Data schema owns fields/tables/versions/migrations. Security spec owns invariants and fail-open/fail-closed rules. Plan owns scope/sequence/gates/dependencies/handoff. Tasks/gate/reports are historical evidence only.

Gap:
A Phase 3 executor had no Phase 3-specific rule preventing reports or historical tasks from becoming authority.

Risk:
Historical `PHASE_2_TASKS.yaml` or gate reports could be misused as dispatch authority.

Required improvement:
Put the authority model directly in `PHASE_3_PLAN.md` and task contracts.

Blocking status:
`BLOCKING_FOR_IMPLEMENTATION`; documentation can repair it.

## Evidence Framework

Current Phase 3 state:
No Phase 3 evidence vocabulary existed.

Expected state:
Phase 3 must not mix `DOCUMENTED`, `VERIFIED_DOCUMENTATION`, `IMPLEMENTED`, `TESTED`, and `NOT_VERIFIED`.

Gap:
A future executor could overclaim implementation from documentation-only artifacts.

Risk:
Phase 3 could be reported as complete without direct code/test evidence.

Required improvement:
Add evidence states to the plan and validation checklist. Require evidence artifacts per task.

Blocking status:
`BLOCKING_FOR_IMPLEMENTATION`; documentation can repair it.

## Task-Contract Framework

Current Phase 3 state:
No Phase 3 executable task contracts existed.

Expected state:
Every executable task must include task_id, goal, dependencies, blocked_if, affected_files, allowed_paths, must_not_modify, inputs, outputs, implementation_steps, acceptance_criteria, test_cases, test_commands, evidence_artifact, rollback_strategy, definition_of_done, and status.

Gap:
No task contract existed for Phase 3.

Risk:
Implementation could proceed without dependencies, rollback strategy, validation, or allowed path constraints.

Required improvement:
Create `PHASE_3_TASKS.yaml` with complete task contracts and readiness classification.

Blocking status:
`BLOCKING_FOR_IMPLEMENTATION`; documentation/task creation can proceed.

## Safety Framework

Current Phase 3 state:
No Phase 3 security spec existed.

Expected state:
Phase 3 must not weaken agent connected DB strict read-only, user query permission + safety + confirmation + audit pre-write, raw secret restrictions, high-risk pre-audit fail-closed behavior, DBMS-specific validation, or the no-report-as-authority rule.

Gap:
No Phase 3-specific safety gates existed.

Risk:
A Phase 3 implementation could accidentally enable real SQL, external providers, destructive operations, or raw secret exposure.

Required improvement:
Create `PHASE_3_SECURITY_SPEC.md` and reference it from the plan/tasks/checklist.

Blocking status:
`BLOCKING_FOR_IMPLEMENTATION`; documentation can repair it.

## Phase 2 Dependency Framework

Current Phase 3 state:
Phase 2 documentation is `PASS_WITH_OPEN_DECISIONS`; original implementation foundation is `COMPLETED_BY_HISTORICAL_EVIDENCE`; final Phase 2 refinement implementation is `NOT_VERIFIED`.

Expected state:
Phase 3 must explicitly mark tasks that depend on unverified Phase 2 final refinements as `BLOCKED_BY_PHASE_2_DELTA`.

Gap:
No Phase 3 artifact had dependency classifications.

Risk:
Phase 3 could assume runtime/audit v2, provenance, snapshots, locks, atomic confirmation, audit repair fields, profile migration, or migration errors exist when they are still unverified.

Required improvement:
Create task classification and blockers in the Phase 3 plan and tasks.

Blocking status:
`BLOCKING_FOR_IMPLEMENTATION`; not blocking for documentation.
