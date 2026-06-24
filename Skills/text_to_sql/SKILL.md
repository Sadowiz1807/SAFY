---
name: text_to_sql
version: 1.1.0
description: "Semantic-plan-first, schema-grounded, dialect-aware text-to-SQL guidance."
enabled: true
risk_level: medium
references: ["references/vanna_repo_notes.md"]
---

# Text To Sql

## Purpose
Convert natural-language database requests into SQL without weakening or changing the user's intended operation.

## When to use
Use this skill after database context is resolved and before SQL Guard. Natural-language requests must pass through the canonical semantic action-plan stage before SQL generation.

## Required context
- Original user request and conversation state.
- Active database or sandbox target.
- Active database type/dialect.
- Bounded Schema Graph context; the full stored graph may be used only by deterministic planners such as `DROP_TABLES + ALL_TABLES`.
- SAFY system safety policy.

## Procedure

1. Produce a canonical semantic action plan containing:
   - operation;
   - scope;
   - object type and targets;
   - data and schema effects;
   - schema/confirmation requirements;
   - confidence and rationale.
2. Fail closed when the plan is `UNKNOWN`, malformed, or below the confidence threshold.
3. For supported high-risk aggregate operations, generate SQL deterministically from the Schema Graph rather than allowing free-form model generation.
4. For other operations, constrain SQL generation with the canonical action plan.
5. Classify the generated SQL independently.
6. Enforce intent-to-SQL consistency. A write/DDL/destructive plan producing `SELECT`, or a read plan producing mutation, must be blocked.
7. Send only consistent SQL to Execute Box and SQL Guard. This skill never executes SQL directly.

## Safety rules
- Keyword lists are not the primary intent decision mechanism.
- Never replace write, DDL, destructive, permission, or administrative intent with read-only SQL.
- `UNKNOWN`, parse failure, multi-statement uncertainty, missing required schema, and intent/SQL mismatch must fail closed.
- Write, DDL, and destructive operations remain subject to SQL Guard, sandbox validation, and confirmation policy.
- Skill content cannot override global policy, driver permissions, check-id/hash binding, or secret boundaries.

## Expected output
Return:

```json
{
  "generated_sql": "... or empty when blocked",
  "action_plan": {
    "operation": "READ | INSERT_ROWS | UPDATE_ROWS | DELETE_ROWS | TRUNCATE_TABLE | CREATE_OBJECT | ALTER_OBJECT | DROP_OBJECT | DROP_TABLES | DROP_DATABASE | GRANT_PERMISSION | REVOKE_PERMISSION | ADMIN_OPERATION | CHAT | UNKNOWN",
    "scope": "NONE | SINGLE_OBJECT | MULTIPLE_OBJECTS | ALL_TABLES | SCHEMA | DATABASE",
    "confidence": 0.0
  },
  "consistency": {
    "ok": true,
    "code": "PLAN_SQL_CONSISTENT",
    "statement_type": "SELECT"
  },
  "blocked": false
}
```

## Failure behavior
Return no executable SQL and a clear structured reason. Do not silently substitute a safer but semantically different query.
