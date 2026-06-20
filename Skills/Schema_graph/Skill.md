---
name: Schema_graph
description: "Loads, refreshes, deletes, and summarizes persisted schema graphs."
version: 1
status: active
intent: schema_graph
targets: [connected_database, sandbox]
redaction_profile: database_safe
requires_active_database: false
auto_execute: false
---


Schema graph skill.

Rules:
- Store many schema graphs by database_profile_id.
- Active database determines the active schema.
- Do not introspect on every chat.
- Refresh schema only when user triggers refresh.
- Missing schema is an empty state, not an error.

