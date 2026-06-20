---
name: Text_to_query
description: "Generates SQL drafts from user requests using active database schema context."
version: 1
status: active
intent: text_to_query
targets: [connected_database, sandbox]
redaction_profile: database_safe
requires_active_database: false
auto_execute: false
---


Text-to-query skill.

Rules:
- Generate SQL draft only.
- Never execute SQL.
- Use active database schema graph when available.
- Prefer SELECT.
- DDL/DML can be drafted for review but SQL Guard decides execution.
- Return structured SQL draft payload.

