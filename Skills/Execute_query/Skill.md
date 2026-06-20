---
name: Execute_query
description: "Executes a previously checked read-only query."
version: 1
status: active
intent: execute_query
targets: [connected_database, sandbox]
redaction_profile: database_safe
requires_active_database: false
auto_execute: false
---


Execute query skill.

Rules:
- Requires check_id and sql_hash from query_guard.
- Executes only after user-controlled Check Safety.
- Does not persist result rows.

