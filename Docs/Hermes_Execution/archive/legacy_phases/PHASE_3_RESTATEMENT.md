# Phase 3 Restatement

## 1. What Phase 3 Is Trying To Achieve

Phase 3 is intended to turn Safy's verified planning framework into a coherent implementation-ready execution layer without weakening the Phase 2 safety boundary. Because no existing Phase 3 artifacts were found, Phase 3 starts as planning and task-contract generation, not as product-complete implementation.

The expected product direction remains:

- LLM suggests.
- Safy verifies.
- Sandbox tests.
- Policy decides.
- Audit records.
- User explicitly authorizes risky manual actions.

Phase 3 must define concrete task contracts for implementation and hardening while respecting that final Phase 2 refinements are still `NOT_VERIFIED` in code/tests.

## 2. In Scope

Phase 3 planning scope includes:

- Creating `PHASE_3_PLAN.md`.
- Creating `PHASE_3_TASKS.yaml`.
- Creating `PHASE_3_CONTRACTS.md`.
- Creating `PHASE_3_SECURITY_SPEC.md` if needed by Phase 3-specific safety gates.
- Creating `PHASE_3_VALIDATION_CHECKLIST.md`.
- Classifying each executable task as `READY_TO_IMPLEMENT`, `BLOCKED_BY_PHASE_2_DELTA`, `BLOCKED_BY_USER_DECISION`, `DOCUMENTATION_ONLY`, or `DEFERRED`.
- Separating documentation evidence from implementation/test evidence.
- Defining how Phase 3 must consume Phase 2 outputs without pretending that unverified Phase 2 delta refinements already exist.

Potential implementation scope is limited to tasks that are explicitly `READY_TO_IMPLEMENT` after plan improvement and do not require real connected-database execution, destructive database operations, external provider calls, or unverified Phase 2 dependencies.

## 3. Out Of Scope

Phase 3 must not currently claim or execute:

- Real sub-agent dispatch.
- Parallel agent execution.
- Real connected-database SQL execution.
- Destructive database operations.
- Real external provider calls.
- Phase 3 implementation based on unverified Phase 2 delta capabilities.
- Phase 3 dispatch as complete without direct implementation and test evidence.
- Phase 2 final refinement implementation as complete.

## 4. Expected Artifacts

Required or expected Phase 3 artifacts:

- `Docs/Hermes_Execution/PHASE_3_RESTATEMENT.md`.
- `Docs/Hermes_Execution/PHASE_3_FRAMEWORK_COMPARISON.md`.
- `Docs/Hermes_Execution/PHASE_3_PLAN.md`.
- `Docs/Hermes_Execution/PHASE_3_TASKS.yaml`.
- `Docs/Hermes_Execution/PHASE_3_CONTRACTS.md`.
- `Docs/Hermes_Execution/PHASE_3_SECURITY_SPEC.md`.
- `Docs/Hermes_Execution/PHASE_3_VALIDATION_CHECKLIST.md`.

Reports generated during or after Phase 3 live under `Docs/Hermes_Execution/report/` and are evidence-only.

Existing Phase 3 artifact status before Mode 1:

- `PHASE_3_PLAN.md`: `NOT_FOUND`.
- `PHASE_3_TASKS.yaml`: `NOT_FOUND`.
- `PHASE_3_CONTRACTS.md`: `NOT_FOUND`.
- `PHASE_3_SECURITY_SPEC.md`: `NOT_FOUND`.
- `PHASE_3_VALIDATION_CHECKLIST.md`: `NOT_FOUND`.

## 5. Phase 2 Outputs Phase 3 Depends On

Phase 3 depends on:

- `SAFY_source.md` for product intent, architecture, policy boundaries, module ownership, and safety model.
- `PHASE_2_PLAN.md` for Phase 2 scope, sequence, gates, dependencies, handoff, and dispatch boundary.
- `PHASE_2_CONTRACTS.md` for interface contracts, normalized errors, lifecycle rules, atomicity, concurrency, and fail-closed behavior.
- `PHASE_2_DATA_SCHEMA_SPEC.md` for profile JSON schema, runtime DB schema, audit DB schema, schema versioning, and migration rules.
- `PHASE_2_SECURITY_SPEC.md` for security invariants, raw secret constraints, connected-DB safety, high-risk confirmation, audit pre-write, and fail-open/fail-closed rules.
- `PHASE_2_VALIDATION_CHECKLIST.md` for evidence classification boundaries.
- Historical reports only as evidence for the original foundation; reports are not required inputs or authority.
- `PHASE_2_IMPLEMENTATION_DELTA_PLAN.md` for unverified final refinement tasks and dependencies.
- `PHASE_2_ARTIFACT_CONSISTENCY_MATRIX.md` for documented consistency decisions and open decisions.
- `PHASE_2_FINAL_ACCEPTANCE_CHECKLIST.md` for final Phase 2 documentation acceptance status and Phase 3 dispatch boundary.

## 6. Phase 2 Final Refinements That Are NOT_VERIFIED But Relevant

Phase 3 must not silently assume these exist:

- Runtime/audit schema v2.
- `workflow_object_provenance`.
- `schema_snapshots`.
- `workspace_locks`.
- Atomic `validate_and_reserve` confirmation lifecycle.
- Audit repair fields and transitions.
- Profile container migration.
- `user_query_access_mode` migration.
- Canonical migration error behavior.

If a Phase 3 task needs any of these, the task must be marked `BLOCKED_BY_PHASE_2_DELTA` or converted into a Phase 2 prerequisite/hardening task.

## 7. What Must Not Be Executed Yet

The following must not be executed unless explicitly authorized and supported by evidence:

- Real connected-database SQL.
- Destructive database operation.
- Real external provider call.
- Phase 3 implementation relying on Phase 2 delta items marked `NOT_VERIFIED`.
- Phase 3 dispatch beyond documentation/task-contract planning.
- Any task marked `BLOCKED_BY_PHASE_2_DELTA`, `BLOCKED_BY_USER_DECISION`, or `DEFERRED`.

## 8. User Decisions That Remain Open

Open decisions that affect Phase 3 planning or execution:

- Confirmation persistence backend for target deployment.
- Runtime/audit generated artifact policy.
- Confirmation TTL and attempt limit.
- Windows locking implementation.
- Audit retention duration.
- Explicit approval for any Phase 3 implementation dispatch.
- Explicit approval for any real connected-database execution.
- Explicit approval for any destructive database operation.

## 9. What Counts As Phase 3 Success

Phase 3 success at the current stage means:

- Phase 3 scope is clearly restated.
- Phase 3 is compared against the Safy product, authority, evidence, task-contract, and safety frameworks.
- Missing Phase 3 artifacts are created coherently.
- Every task has a complete executable task contract.
- Every task is honestly classified by readiness/blocker status.
- No task assumes unverified Phase 2 delta implementation.
- Any executed task is limited to `READY_TO_IMPLEMENT` work and has direct evidence.
- Two simulated read-only review passes are completed without real sub-agents.
- Final report uses honest status vocabulary and does not overclaim completion.

## 10. What Counts As Unsafe Overclaim

Unsafe overclaim includes:

- Saying Phase 3 is complete when only documentation was created.
- Treating Phase 2 documentation acceptance as code/test evidence.
- Treating historical Phase 2 foundation evidence as proof of final Phase 2 delta implementation.
- Marking `NOT_VERIFIED` Phase 2 dependencies as implemented without direct tests.
- Dispatching from historical `PHASE_2_TASKS.yaml`.
- Using reports as architectural authority.
- Claiming connected-database execution safety without audit pre-write, permission check, confirmation, and fail-closed behavior.
- Claiming high-risk code confirmation is safe without atomic reserve/consume evidence.
- Claiming production readiness while open decisions remain unresolved.


## Execution Readiness Boundary

Phase 3 execution is blocked until Phase 2 delta implementation is verified with direct evidence and explicit user approval. Phase 3 planning artifacts may be synchronized now, but they must not be treated as permission to implement or dispatch Phase 3 tasks.
