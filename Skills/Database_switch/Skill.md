---
name: Database_switch
description: "Switches the active database profile without parsing database names from prompts."
version: 1
status: active
intent: database_switch
targets: [connected_database, sandbox]
redaction_profile: database_safe
requires_active_database: false
auto_execute: false
---


Database switching skill.

Rules:
- The user changes database through UI/API switch only.
- Text prompts do not switch active database.
- When switched, SAFY loads the stored schema graph if it exists.
- If no schema graph exists, UI shows an empty schema window without warning.

