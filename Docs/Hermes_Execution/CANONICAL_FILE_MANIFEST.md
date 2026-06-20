# Canonical File Manifest

## Rule
When duplicate uploaded/cache filenames exist, local canonical filenames without suffix are authoritative if present. Files with suffixes such as (1), (2), (3) are not canonical unless explicitly renamed/merged by user.

## Canonical Current Files
- `Docs/Hermes_Execution/00_PROJECT_BRIEF.md`
- `Docs/Hermes_Execution/01_AGENT_ROSTER.md`
- `Docs/Hermes_Execution/02_FILE_OWNERSHIP.md`
- `Docs/Hermes_Execution/03_STAGE_PLAN.md`
- `Docs/Hermes_Execution/04_TASK_BOARD.yaml`
- `Docs/Hermes_Execution/05_HANDOFF_PROTOCOL.md`
- `Docs/Hermes_Execution/06_VALIDATION_GATES.md`
- `Docs/Hermes_Execution/07_CONFLICT_POLICY.md`
- `Docs/Hermes_Execution/08_STAGE_REPORT_TEMPLATE.md`
- `Docs/Hermes_Execution/STAGE_0_PLAN.md`
- `Docs/Hermes_Execution/STAGE_0_TASKS.yaml`
- `Docs/Hermes_Execution/STAGE_1_API_MOCK_SPEC.md`
- `Docs/Hermes_Execution/STAGE_1_CONTRACTS.md`
- `Docs/Hermes_Execution/STAGE_1_PLAN.md`
- `Docs/Hermes_Execution/STAGE_1_TASKS.yaml`
- `Docs/Hermes_Execution/STAGE_1_UI_SPEC.md`
- `Docs/Hermes_Execution/STAGE_1_VALIDATION_CHECKLIST.md`
- `Docs/Hermes_Execution/STAGE_2_ARTIFACT_CONSISTENCY_MATRIX.md`
- `Docs/Hermes_Execution/STAGE_2_CONTRACTS.md`
- `Docs/Hermes_Execution/STAGE_2_DATA_SCHEMA_SPEC.md`
- `Docs/Hermes_Execution/STAGE_2_FINAL_ACCEPTANCE_CHECKLIST.md`
- `Docs/Hermes_Execution/STAGE_2_IMPLEMENTATION_DELTA_PLAN.md`
- `Docs/Hermes_Execution/STAGE_2_MAIN_AGENT_DECISION_LEDGER.md`
- `Docs/Hermes_Execution/STAGE_2_PLAN.md`
- `Docs/Hermes_Execution/STAGE_2_SECURITY_SPEC.md`
- `Docs/Hermes_Execution/STAGE_2_TASKS.yaml`
- `Docs/Hermes_Execution/STAGE_2_VALIDATION_CHECKLIST.md`
- `Docs/Hermes_Execution/STAGE_3_CONTRACTS.md`
- `Docs/Hermes_Execution/STAGE_3_FRAMEWORK_COMPARISON.md`
- `Docs/Hermes_Execution/STAGE_3_PLAN.md`
- `Docs/Hermes_Execution/STAGE_3_RESTATEMENT.md`
- `Docs/Hermes_Execution/STAGE_3_SECURITY_SPEC.md`
- `Docs/Hermes_Execution/STAGE_3_TASKS.yaml`
- `Docs/Hermes_Execution/STAGE_3_VALIDATION_CHECKLIST.md`

## Historical Reports Retained Under report/
- `Docs/Hermes_Execution/report/P0-BRIEF-001.md`
- `Docs/Hermes_Execution/report/P0-ROSTER-001.md`
- `Docs/Hermes_Execution/report/P1-API-MOCK-001.md`
- `Docs/Hermes_Execution/report/P1-PROFILE-CONTRACT-001.md`
- `Docs/Hermes_Execution/report/P1-UI-SHELL-001.md`
- `Docs/Hermes_Execution/report/P2-AUDIT-DB-REDACTION-001.md`
- `Docs/Hermes_Execution/report/P2-CONFIG-LOADER-001.md`
- `Docs/Hermes_Execution/report/P2-ENV-WRITER-SECRET-RESOLVER-001.md`
- `Docs/Hermes_Execution/report/P2-HIGH-RISK-CODE-STATE-001.md`
- `Docs/Hermes_Execution/report/P2-PROFILE-API-INTEGRATION-001.md`
- `Docs/Hermes_Execution/report/P2-PROFILE-STORAGE-001.md`
- `Docs/Hermes_Execution/report/P2-RUNTIME-DB-001.md`
- `Docs/Hermes_Execution/report/P2-UI-PROFILE-INTEGRATION-001.md`
- `Docs/Hermes_Execution/report/STAGE_0_TO_3_ARTIFACT_CLASSIFICATION.md`
- `Docs/Hermes_Execution/report/STAGE_0_TO_3_REMAINING_ISSUE_INVENTORY.md`
- `Docs/Hermes_Execution/report/STAGE_0_TO_3_REPORT_CLEANUP_DELETION_MANIFEST.md`
- `Docs/Hermes_Execution/report/STAGE_0_TO_3_REPORT_REFERENCE_INVENTORY.md`
- `Docs/Hermes_Execution/report/STAGE_0_TO_3_REPORT_STRUCTURE_CLEANUP_VALIDATION.md`

## Deleted Files
- `STAGE_0_GATE_REPORT.md`
- `STAGE_1_GATE_REPORT.md`
- `STAGE_2_FINAL_CONSISTENCY_REPORT.md`
- `STAGE_2_GATE_REPORT.md`
- `STAGE_2_SUBAGENT_EXECUTION_CONFLICT_REPORT.md`
- `STAGE_3_EXECUTION_LOG.md`
- `STAGE_3_FINAL_REPORT.md`

## Archive-Only Files
- None identified beyond retained historical reports.

## Duplicate/Stale Files Ignored
- Uploaded/cache files with suffixes `(1)`, `(2)`, `(3)` are non-canonical unless explicitly renamed/merged by user.

## Source-of-truth hierarchy

1. `SAFY_source.md` owns product intent, architecture, policy boundaries, and module ownership.
2. Stage root artifacts under `Docs/Hermes_Execution/` own current planning/contracts/checklists.
3. Files under `Docs/Hermes_Execution/report/` are evidence-only and never override root artifacts or `SAFY_source.md`.

