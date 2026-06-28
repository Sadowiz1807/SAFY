---
name: create_database
version: 2.0.0
description: "Classifies a business domain from compiled DomainIntelligence packs and creates a guarded multi-table DDL draft for the user-controlled Execute Box."
enabled: true
risk_level: high
references: []
policy:
  allowed_intents: [create_domain_schema, list_domain_catalog]
  allowed_targets: [connected_database]
  allowed_toolsets: [domain, sql, sandbox, database, ui]
  allowed_tools:
    - domain.schema.design
    - execute_box.set_draft
    - sql.guard
    - sandbox.validate
    - database.execute
  denied_tools:
    - connected_database.agent_write
    - provider.network
    - database.server_admin
  allowed_statement_classes: [CREATE, BATCH]
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
    - TRANSACTION_CONTROL
  sandbox_only: false
  sandbox_then_real: true
  sql_guard_required: true
  audit_required: true
  max_steps: 24
  timeout_seconds: 60
  redaction_profile: agent_runtime-default
  confirmation_behavior: execute_box_user_confirmation_after_sandbox_pass
---

# Create Database

## Purpose
Design a normalized multi-table relational schema from the canonical compiled packs in `DomainIntelligence/packs/`, then place a validated DDL batch in the Execute Box. In SAFY, “create database” means creating the schema objects required by a business domain. It does not mean issuing the server-level `CREATE DATABASE` statement.

## When to use
Use this skill for requests to design or create an entire business-domain database/schema with multiple related tables, or to list the domain schema types SAFY can design. Do not use it for one isolated table, querying existing data, or server-level database administration.

## Required context
- Current user request and pending clarification state.
- Active model profile for semantic classification and schema design.
- Canonical compiled DomainIntelligence catalog.
- Active tested database profile and dialect for `/Execute`.
- Query Guard, sandbox and Execute Box contracts.

## Procedure
Follow the semantic routing and user workflows below. The active runtime must resolve the domain, validate every generated statement, place the exact batch in Execute Box, and defer all execution to Check Safety and explicit user Execute.

## Runtime authority
`Agent/agent_runtime.py` is the only active chat runtime. The skill uses `DomainIntelligence/schema_workflow.py`; no legacy AgentCore pipeline is used.

## Semantic routing
- Classify the request semantically with the active model and the complete compiled-domain catalog.
- Do not require one fixed keyword list.
- Automatically select a domain only when the request is sufficiently clear and confidence is at least the runtime threshold.
- If the request is broad, has multiple plausible domains, or contains an uncertain typo, ask the user to select/clarify.
- Never default to e-commerce.
- The list of supported domains comes only from `DomainIntelligence/packs/registry.json`.

## User workflows

### Normal chat
1. Classify or clarify the domain.
2. Return a domain preview and representative entities.
3. Do not generate executable SQL.
4. Tell the user to use `/Execute` to request a DDL draft.

### `/Execute`
1. Require an active, tested application database profile so the target dialect is known.
2. Reject SQL Server system databases as application grounding.
3. Load the selected compiled DomainIntelligence pack.
4. Generate a bounded multi-table DDL batch using only `CREATE TABLE` and optional `CREATE INDEX`.
5. Deterministically reject `CREATE DATABASE`, DROP, TRUNCATE, ALTER, DML, permission/admin, transaction-control, function/procedure/trigger, and unknown statements.
6. Place the DDL in the Execute Box; do not execute automatically.
7. The user reviews the SQL and runs Check Safety.
8. Check Safety validates the exact batch in the profile-bound sandbox.
9. Only a sandbox-passed, exact-bound, unconsumed check can be executed on the connected database after the user presses Execute.

## Safety rules
- Never default to a domain.
- Never issue server-level `CREATE DATABASE`.
- Never execute generated DDL directly from chat.
- Allow only bounded CREATE TABLE/INDEX batches.
- Require exact context binding and sandbox validation before real execution.
- Preserve the existing DROP/TRUNCATE/admin/security blocks.

## Expected output
Return the normal SAFY response envelope with:
- domain resolution and evidence;
- generated multi-statement DDL when `/Execute` is used;
- exact target/profile/dialect/context binding;
- `sandbox_required=true`;
- `server_level_create_database=false`;
- no check ID or execution until the user runs Check Safety.

## Failure behavior
Fail closed. Ask a clarification question for ambiguous domain requests. Return a stable error for missing profile, unsupported dialect/domain pack, invalid model JSON, unsafe SQL, unresolved statement target, or sandbox failure. Never invent an unsupported domain or silently switch the target.
