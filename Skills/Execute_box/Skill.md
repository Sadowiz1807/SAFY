---
name: Execute_box
description: "Formats generated SQL as a reviewable Execute Box draft."
version: 1
status: active
intent: execute_box
targets: [connected_database, sandbox]
redaction_profile: database_safe
requires_active_database: false
auto_execute: false
---


Execute Box skill.

Rules:
- Receives SQL draft.
- Does not run SQL.
- Tells UI to place SQL into Execute Box.
- User must press Check Safety and Execute manually.

