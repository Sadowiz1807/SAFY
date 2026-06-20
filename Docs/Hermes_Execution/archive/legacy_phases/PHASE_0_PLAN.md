# Phase 0 Plan - Context Loading and Contract Freeze

Source of truth: `C:/Users/ASUS/SAFY/Docs_prior_project/SAFY_source.md`

Status: historical completed gate, documentation-only. No implementation is authorized by this file.

## Objective
Freeze the orchestration context before implementation work: project brief, source-of-truth precedence, agent roster, file ownership, task-board schema gate, handoff protocol, validation gates, and conflict policy.

## Canonical Inputs
- `SAFY_source.md`
- `HERMES_MAIN_AGENT_EXECUTION_PLAN.md`
- User decisions preserved in Phase 0 project brief and gate report

## Outputs In This Folder
Core deliverables:
- `00_PROJECT_BRIEF.md`
- `01_AGENT_ROSTER.md`
- `02_FILE_OWNERSHIP.md`
- `03_PHASE_PLAN.md`
- `04_TASK_BOARD.yaml`
- `05_HANDOFF_PROTOCOL.md`
- `06_VALIDATION_GATES.md`
- `07_CONFLICT_POLICY.md`
- `08_PHASE_REPORT_TEMPLATE.md`
- `report/P0-BRIEF-001.md`
- `report/P0-ROSTER-001.md`

Historical reports:
- Reports, if retained, live under `Docs/Hermes_Execution/report/` and are evidence only.

## Non-negotiable Decisions
- `SAFY_source.md` wins over older or derived files.
- Agent connected database path remains strict read-only.
- User query path is separate from agent path and requires safety checks, confirmation when needed, and audit.
- Raw secrets must not be returned, logged, audited, or stored in JSON.
- UI remains chat-first with left sidebar, main chat area, and right execution sidebar.

## Gate 0 Requirements
Dispatchable task entries must include task id, title, phase, assigned agent, priority, status, dispatchability, input docs, allowed paths, forbidden paths, requirements, acceptance criteria, validation gate, handoff artifact, and definition of done.

## Flat Directory Rule
All Phase 0 artifacts are stored directly in `Docs/Hermes_Execution/`; do not create or reference a phase-report sub-folder.

## Known Historical Fix
The original Phase 0 task board was too high-level. It was corrected by adding Gate 0 and rebuilding executable task contracts before Phase 1 dispatch.
