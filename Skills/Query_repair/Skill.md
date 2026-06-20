---
name: Query_repair
description: "Repairs SQL drafts after guard or driver errors using schema context."
version: 1
status: active
intent: query_repair
targets: [connected_database, sandbox]
redaction_profile: database_safe
requires_active_database: false
auto_execute: false
---


Query repair skill.

Rules:
- Repair SQL draft only.
- Do not execute repaired SQL.
- Return repaired draft to Execute Box.

