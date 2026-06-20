# Phase 10 Requirements

Target release: `v1.2.0 Real DB Driver Read-only`.

- Driver priority: MySQL -> PostgreSQL -> SQLite.
- All three drivers must pass; MySQL/PostgreSQL use Docker-backed validation.
- Allowed SQL: SELECT, WITH ... SELECT, SHOW, DESCRIBE, EXPLAIN SELECT.
- Block INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, REPLACE, MERGE, CALL, EXEC, GRANT, REVOKE, LOAD DATA, COPY, DDL, writes.
- Credentials come from environment variable names; profiles store `password_env`, not password values.
- `/query/check` analyzes only and never connects.
- `/query/execute` requires `check_id`, `sql_hash`, `database_profile_id`, and target binding.
- Row limit defaults to 50; timeout defaults to 90 seconds.
- Query result rows are temporary HTTP response data only.
- Agent auto SELECT must use `/query/check` -> `/query/execute`.
