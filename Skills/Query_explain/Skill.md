---
name: Query_explain
description: "Explains SQL using schema graph context without executing it."
version: 1
status: active
intent: query_explain
targets: [connected_database, sandbox]
redaction_profile: database_safe
requires_active_database: false
auto_execute: false
---


Query explain skill.

Rules:
- Explain intent, tables, joins, filters, and safety implications.
- Never execute SQL.

