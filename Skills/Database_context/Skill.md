---
name: Database_context
description: "Resolves the single active database context used by all DB workflows."
version: 1
status: active
intent: database_context
targets: [connected_database, sandbox]
redaction_profile: database_safe
requires_active_database: false
auto_execute: false
---


Resolves SAFY's active database context.

Rules:
- One active database at a time.
- Prompt text must not switch database names.
- Database switch is a UI/backend action only.
- Query generation and execution use the active database profile.

