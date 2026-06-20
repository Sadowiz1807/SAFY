---
name: Query_guard
description: "Checks SQL with SAFY SQL Guard before execution."
version: 1
status: active
intent: query_guard
targets: [connected_database, sandbox]
redaction_profile: database_safe
requires_active_database: false
auto_execute: false
---


Query guard skill.

Rules:
- All SQL execution must go through this skill.
- Read-only mode is the default.
- Guard checks do not execute SQL.
- Guard output is required before execute_query.

