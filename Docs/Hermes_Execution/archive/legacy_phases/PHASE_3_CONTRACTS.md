# Phase 3 Contracts

## 1. Contract Purpose

These contracts define Phase 3 execution obligations. They do not replace Phase 2 contracts; they add Phase 3-specific planning, dependency, review, and evidence rules.

## 2. Execution Mode Contract

Inputs:
- User-approved single-agent Phase 3 prompt.
- Canonical Safy and Phase 2 artifacts.

Outputs:
- Phase 3 core planning, task, validation, security, and contract artifacts.
- Optional reports/review summaries, if generated, live under `Docs/Hermes_Execution/report/` and are evidence-only.

## 3. Dependency Classification Contract

Each task must be classified as one of:

- `READY_TO_IMPLEMENT`.
- `BLOCKED_BY_PHASE_2_DELTA`.
- `BLOCKED_BY_USER_DECISION`.
- `DOCUMENTATION_ONLY`.
- `DEFERRED`.

A task is `BLOCKED_BY_PHASE_2_DELTA` if it requires any Phase 2 final refinement still marked `NOT_VERIFIED`.

A task is `BLOCKED_BY_USER_DECISION` if it needs an unresolved product/security/deployment decision or explicit real execution approval.

## 4. Evidence Contract

Evidence states:

- `DOCUMENTED`: written in a doc.
- `VERIFIED_DOCUMENTATION`: directly checked against docs.
- `IMPLEMENTED`: code exists and is linked to task evidence.
- `TESTED`: command/test evidence exists.
- `NOT_VERIFIED`: no direct code/test evidence.

Documentation must not be reported as runtime implementation evidence.

## 5. Safety Contract

Phase 3 must preserve:

- Agent connected DB strict read-only.
- User query permission + safety check + explicit confirmation + high-risk challenge if required + audit pre-write.
- Raw secret exclusion from JSON/API/log/frontend/audit output.
- High-risk pre-audit fail-closed behavior.
- DBMS-specific SQL validation; no SQLite fallback validation for PostgreSQL/MySQL.
- Reports as evidence only, not authority.

## 6. Review Contract

Review pass 1 and pass 2 are read-only simulated reviewer modes. They must check scope drift, Phase 2 dependency misuse, security regression, permission regression, raw secret leakage, accidental real execution, broken paths, missing tests, failing commands, stale report authority, task overclaim, documentation/code mismatch, bug risk, runtime error risk, and unhandled open decisions.

P0/P1 in pass 2 blocks the final PASS report and requires user input.


## Execution Readiness Boundary

Phase 3 execution is blocked until Phase 2 delta implementation is verified with direct evidence and explicit user approval. Phase 3 planning artifacts may be synchronized now, but they must not be treated as permission to implement or dispatch Phase 3 tasks.
