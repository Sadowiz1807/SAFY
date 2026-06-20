# Safy Skills Specification

## Purpose
Define Safy's skill system, Skill.md format, SkillPolicy compilation, core skill workflows, SkillResult contract, and skill safety rules.

## Scope
Covers Create_database, Text_to_sql, Read_schema, Explain_query, frontmatter policy fields, and deterministic enforcement boundaries.

## Source Reference
Source-of-truth: `SAFY_source.md`.

## 1. Skill System Overview
Skills are workflow instructions and structured behavior descriptions. They help the agent plan, but they are not enforcement by themselves. Enforcement comes from compiled SkillPolicy, ToolRegistry, SQL Guard, Permission Checker, and runtime policy.

## 2. Skill.md Format
Recommended `Skill.md` sections:
- Title.
- Purpose.
- Trigger conditions.
- Inputs.
- Workflow steps.
- Allowed targets.
- Allowed tools/toolsets.
- Output contract.
- Safety rules.
- Examples.

## 3. Skill Frontmatter
Example:

```yaml
---
name: Create_database
version: 1.0.0
allowed_toolsets:
  - sql_guard
  - sandbox
allowed_execution_targets:
  - sandbox
allowed_statement_classes:
  - select
  - insert
  - update
  - delete
  - create
  - alter
  - drop_owned_workspace_object_for_rollback
blocked_statement_classes:
  - connected_database_write
  - server_admin
risk_ceiling: sandbox_high
requires_sandbox: true
confirmation_behavior: policy_driven
---
```

## 4. SkillPolicy Compilation
Skill frontmatter compiles into deterministic SkillPolicy. Required fields:

```txt
allowed_toolsets
allowed_execution_targets
allowed_statement_classes
blocked_statement_classes
risk_ceiling
requires_sandbox
confirmation_behavior
```

Additional rollback provenance fields:

```txt
created_by_workflow_id
created_step_id
rollback_allowed_until_status
workspace_id
object_type
object_name
```

Rules:
- Skill.md is workflow instruction, not enforcement by itself.
- LLM cannot override SkillPolicy.
- SkillPolicy must be checked before tool execution.
- Rollback/drop of owned objects requires object-level provenance in `workflow_object_provenance`.

## 5. Create_database Skill
Required workflow:
1. Analyze requirement.
2. Detect domain.
3. Load domain rule pack.
4. Extract entities.
5. Extract attributes.
6. Classify business rules.
7. Decide enforcement layer.
8. Build logical schema.
9. Generate physical DDL.
10. Sanitize identifiers.
11. Validate SQL.
12. Create sandbox workspace.
13. Execute DDL in sandbox.
14. Read schema back.
15. Build schema snapshot/summary.
16. Return design report and SQL.

Rules:
- Execution target is sandbox.
- Generated SQL must pass SQL Guard.
- PostgreSQL/MySQL use Docker sandbox.
- SQLite runner only for SQLite target.
- `created_objects` must include tables/views/indexes/constraints.

## 6. Text_to_sql Skill
Purpose: Convert user questions into read-only SQL for connected database or sandbox.

Rules:
- Connected database path is read-only.
- SELECT/EXPLAIN only for connected database.
- Apply LIMIT to row-returning SELECT.
- Use schema snapshot when available.
- Block multi-statement connected DB SQL.

## 7. Read_schema Skill
Purpose: Inspect schema metadata from sandbox or connected database.

Rules:
- Read-only only.
- Return schema snapshot structure.
- Do not expose secrets or connection strings.

## 8. Explain_query Skill
Purpose: Explain query plan/performance safely.

Rules:
- EXPLAIN is allowed for connected database when read-only.
- No mutation.
- Apply timeout.
- Audit metadata.

## 9. SkillResult Contract
SkillResult includes:
- `success`
- `skill_name`
- `workflow_id`
- `workspace_id`
- `created_objects`
- `schema_snapshot_id`
- `verification_result`
- `risk_level`
- `warnings`
- optional `sql` only when allowed/redacted.

`created_objects` is canonical and includes tables, views, indexes, and constraints.

## 10. Skill Safety Rules
Rules:
- Skill cannot call tools outside compiled allowed toolsets.
- Skill cannot change execution target after policy compile.
- Skill cannot authorize connected database mutation.
- Skill cannot bypass SQL Guard.
- Skill cannot bypass audit for high-risk Manual SQL; Manual SQL is separate from agent skill workflow.

## Implementation Notes
Implement a SkillPolicy compiler and validate every tool call against compiled policy. Store enough workflow/object provenance for rollback-safe cleanup.

## Related Documents
- `06_DATABASE_DESIGN_POLICY.md`
- `07_DOMAIN_RULE_PACKS.md`
- `09_TOOLS_SPEC.md`
- `10_RUNTIME_AND_SANDBOX_SPEC.md`
