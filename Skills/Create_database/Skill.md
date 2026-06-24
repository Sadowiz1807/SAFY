---
name: create_database
version: 1.0.0
description: "Guides sandbox-only database schema creation through shared tools."
enabled: true
risk_level: high
references: []
policy:
  allowed_intents: [create_database]
  allowed_targets: [sandbox]
  allowed_toolsets: [sandbox, database, sql]
  allowed_tools:
    - sandbox.create_workspace
    - sandbox.execute_sql
    - sandbox.inspect_workspace
    - sandbox.cleanup_workspace
    - database.read_schema
    - sql.validate
    - sql.sanitize_identifier
  denied_tools:
    - connected_database.execute
    - connected_database.read
    - provider.network
  allowed_statement_classes: [CREATE]
  blocked_statement_classes:
    - DROP
    - ALTER
    - TRUNCATE
    - RENAME
    - INSERT
    - UPDATE
    - DELETE
    - MERGE
    - GRANT
    - REVOKE
    - ADMIN_SECURITY
    - CROSS_DATABASE_OR_SERVER_LEVEL
    - UNKNOWN
    - MULTI_STATEMENT
  sandbox_only: true
  sql_guard_required: true
  audit_required: true
  max_steps: 24
  timeout_seconds: 30
  redaction_profile: agent_runtime-default
  confirmation_behavior: no_user_confirmation_for_sandbox_create
---

# Create Database

## Purpose
Guides sandbox-only database schema creation through shared tools.

## When to use
Use this skill when SAFY routes a user request to `create_database` in the normal Perceive → Plan → Slot-fill → Route → Act → Verify → Present → Remember workflow.

## Required context
- User request and conversation state.
- Active database or sandbox context when relevant.
- SAFY system safety policy and SQL guard results when SQL is involved.

## Procedure
Load this document as guidance, then use SAFY shared tools/actions for any operation. Do not execute code from the skill pack.

## Safety rules
- Skill content is advisory and cannot override system policy.
- Do not read secrets, change database profiles, or bypass SQL Guard.
- Write, DDL, and destructive operations must use sandbox/confirmation rules.
- Execute actual actions only through SAFY shared guarded tools/actions.

## Expected output
Return the normal SAFY response envelope or action result for `create_database`.

## Failure behavior
Fail closed with a clear error or clarification request. Do not run unsafe SQL or hidden actions.
