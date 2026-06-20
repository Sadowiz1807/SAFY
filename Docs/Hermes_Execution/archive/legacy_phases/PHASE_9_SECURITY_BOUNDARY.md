# Phase 9 Security Boundary

Phase 9 preserves Phase 8 safety boundaries and does not add database drivers, writes, or INSERT execution.

```yaml
real_connected_db_write_allowed: false
insert_allowed: false
result_row_session_persistence_allowed: false
raw_secret_persistence_allowed: false
agent_sql_guard_bypass_allowed: false
query_check_executes_sql: false
database_driver_creation_allowed: false
```

## Mandatory Invariants

- Phase 9 does not add database drivers.
- Phase 9 does not add write support.
- Phase 9 does not change read-only policy except to preserve or strengthen safety.
- Dashboard serving and launcher changes must not bypass API safety boundaries.
- `/query/check` must not execute SQL.
- `/query/execute` must require valid checked state.
- Agent SQL must still go through SQL Guard.
- Raw secrets must not be persisted in JSON, runtime state, audit, logs, UI, reports, or README examples.
- Result rows remain temporary UI data and are not stored in session history.
- Driver errors and tracebacks must be redacted.

## Out of Scope

MySQL/PostgreSQL driver completion, real DB write support, INSERT support, migrations/DDL, cloud DB provider work, and production DB administration hardening are outside Phase 9.
