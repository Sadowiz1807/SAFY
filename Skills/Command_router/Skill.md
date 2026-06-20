---
name: Command_router
description: "Routes chat messages and slash commands into SAFY workflow intents."
version: 1
status: active
intent: command_router
targets: [connected_database, sandbox]
redaction_profile: database_safe
requires_active_database: false
auto_execute: false
---


Routes the user input into a SAFY workflow command.

Supported primary commands:
- `/Execute`: generate SQL draft only.
- `/Reset_schema`: delete all persisted schema graphs.
- `/Delete_schema`: delete the active database schema graph.
- normal chat: no automatic database execution.

This skill never executes SQL.

