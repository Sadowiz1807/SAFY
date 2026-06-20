---
name: Create_database
version: agent_runtime-create-database-v1
policy:
  allowed_intents: [create_database]
  allowed_targets: [sandbox]
  allowed_toolsets: [sandbox, database, sql]
  allowed_tools: [sandbox.create_workspace, sandbox.execute_sql, sandbox.inspect_workspace, sandbox.cleanup_workspace, database.read_schema, sql.validate, sql.sanitize_identifier]
  denied_tools: [connected_database.execute, connected_database.read, provider.network]
  allowed_statement_classes: [CREATE]
  blocked_statement_classes: [DROP, ALTER, TRUNCATE, RENAME, INSERT, UPDATE, DELETE, MERGE, GRANT, REVOKE, ADMIN_SECURITY, CROSS_DATABASE_OR_SERVER_LEVEL, UNKNOWN, MULTI_STATEMENT]
  sandbox_only: true
  sql_guard_required: true
  audit_required: true
  max_steps: 24
  timeout_seconds: 30
  redaction_profile: agent_runtime-default
  confirmation_behavior: no_user_confirmation_for_sandbox_create
---

# Create_database Skill

## purpose
Create a database schema in a Safy sandbox workspace only.

## when to use
Use for user requests that ask Safy to create, design, initialize, or generate a database/schema.

## toolsets
`sandbox`, `database`, and `sql`.

## workflow
Detect intent, resolve domain, compile SkillPolicy, build minimized provider prompt, validate provider output, validate every SQL statement with SQL Guard, execute only in sandbox, read schema back, audit, and return Safy envelope data.

## allowed actions
Create sandbox workspace, validate SQL, execute validated sandbox DDL, read sandbox schema, summarize result.

## forbidden actions
Connected database execution, connected database read-only query, direct provider execution, bypassing ToolExecutor, bypassing SQL Guard, raw secret handling, admin/server-level SQL.

## output format
Return `chat_id`, `workflow_id`, `intent`, `assumptions`, `execution_target`, `workspace_id`, `status`, `schema_summary`, `created_objects`, `technical_result`, `warnings`, and `next_questions` inside Safy envelope `data`.
