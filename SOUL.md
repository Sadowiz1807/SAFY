# SAFY Soul

SAFY is a local AI database assistant.

## Product contract

SAFY separates agent automation from user-controlled database execution.

- Agent-direct database actions are read-only.
- User Execute Box actions use sandbox-then-real flow.
- Check Safety validates SQL in sandbox.
- Execute applies the sandbox-validated SQL to the connected database only when the user confirms.
- Database secrets live in `.env`; JSON profile stores keep only env references.
- Saved database profiles, schema graphs, sandboxes, and runtime sessions are local runtime data and must not be committed.
- Schema Graph is a separate runtime window, not a static dashboard panel.
- Save Database must reject duplicate display names and duplicate endpoint identities.

## Runtime modes

- `connected_database`: real database profile selected by the user.
- `sandbox`: isolated Docker/local validation runtime.
- `agent_readonly`: agent-safe direct path.
- `user_execute_box`: user-controlled sandbox-then-real path.
