# SAFY Agent Workflow Architecture

SAFY uses a database-specialized workflow rather than a generic LLM-only agent loop. The runtime follows:

```text
Perceive -> Plan -> Slot-fill -> Route -> Act -> Verify -> Present -> Remember
```

## Safety classes

| Class | Route | Auto execute | Sandbox | Confirmation |
|---|---|---:|---:|---:|
| READ_ONLY_SQL | direct read on connected DB | yes | no | no |
| WRITE_SQL | sandbox then real DB | no | yes | yes |
| DDL_SQL | sandbox then real DB | no | yes | yes |
| DESTRUCTIVE_SQL | strong confirmation or block | no | yes | yes |
| SECRET_ACCESS | redact/block | no | no | no |
| UNKNOWN_RISK | clarify/block | no | no | no |

## Runtime state

Agent state persists workflow facts only: current target, pending slots, last SQL, last safety class, last check, last execution summary, and bounded workflow history. Raw secrets and full result rows must never become canonical session state.

## Reviewer layer

The reviewer layer is modeled after Hermes subagent delegation, but it is deterministic and database-safe. Reviewers can veto an unsafe route but cannot execute SQL.
