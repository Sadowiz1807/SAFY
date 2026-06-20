# Phase 8 Requirements

Executed by main-agent only. No sub-agents used.

## Phase 8 goal

User selected:

`Phase 8: Real Connected DB Read-only Adapter`

Phase 8 planning targets real database connectivity for read-only workflows. The planned agent workflow is:

- connect to a real database
- read real schema
- generate SQL against the existing real database
- run real read-only `SELECT` queries when allowed

If a requested operation is blocked, SAFY may generate or display SQL text only as non-executed output with a warning that the user must execute it manually outside SAFY.

## DBMS priority

User selected MySQL first, PostgreSQL second, SQLite third.

Priority order:

1. MySQL
2. PostgreSQL
3. SQLite

## Subphase model

User selected the following subphase structure:

- Phase 8.1: MySQL Real Connected DB Read-only Adapter
- Phase 8.2: PostgreSQL Real Connected DB Read-only Adapter
- Phase 8.3: SQLite Connected File Read-only Adapter

All three DBMS must be planned in the overall Phase 8 package. Implementation remains gated by subphase and user approval.

## Connection environments

User selected:

- local database
- Docker database
- both Docker test DB + user-provided real DB

Planning direction:

- support local MySQL/PostgreSQL first
- support Docker MySQL/PostgreSQL for repeatable integration tests
- support user-provided real DB via profiles and environment-based or transient credentials
- defer cloud DB, SSH tunnel, VPN, proxy, and managed provider connectivity unless later approved

## Credential / secret model

User selected:

- credentials may live in `.env` local
- password may be entered directly through UI/API but must not be persisted

Planning requirements:

- raw DB passwords must not be stored in JSON profile stores
- raw DB passwords must not be stored in runtime DB
- raw DB passwords must not appear in audit records, reports, logs, UI output, session history, or test snapshots
- `.env` local is allowed for developer/local use
- direct UI/API password entry is transient only and must be redacted immediately
- profiles should store env var names or DSN env var names, not raw secrets
- if DSN is supported, DSN-by-env-var is preferred over raw DSN in profile JSON

## Strict read-only policy

INSERT is not part of Phase 8. Phase 8 is strictly read-only. INSERT must be blocked together with other data-changing commands.

Allowed in Phase 8:

- `SELECT`
- schema introspection
- safe metadata queries
- optionally `EXPLAIN` only if guaranteed read-only per DBMS-specific enforcement

Blocked in Phase 8:

- `INSERT`
- `UPDATE`
- `DELETE`
- `DROP`
- `ALTER`
- `TRUNCATE`
- `CREATE`
- `GRANT`
- `REVOKE`
- `COPY`
- `CALL` / stored procedures
- multi-statement SQL
- `SELECT ... FOR UPDATE`
- side-effect functions
- any SQL that changes data, schema, permissions, server state, or locks rows for mutation

## INSERT removed from Phase 8

INSERT is not part of Phase 8. Phase 8 is strictly read-only. INSERT must be blocked together with other data-changing commands.

If the user or agent requests `INSERT`, SAFY may display SQL text as non-executed output with a warning, but SAFY must not execute it.

## Query execution flow

User selected:

`/query/check -> SQL Guard -> confirmation if needed -> /query/execute`

Planning requirements:

- real DB `SELECT` must go through the existing flow
- non-sensitive `SELECT` may execute after check without manual confirmation
- sensitive, broad, or large `SELECT` must require confirmation
- confirmation must remain backend-generated, one-time, expiring, and state-bound
- `/query/check` must not execute SQL
- `/query/execute` must require valid binding to the prior check

## Agent behavior

User selected:

- agent may generate real SQL for the existing database
- agent may work with real schema
- agent may execute allowed read-only `SELECT`
- blocked operations must not be executed
- blocked SQL may be shown with warning only
- agent must inspect real schema before generating SQL

Planning requirements:

- agent must use schema introspection before SQL generation
- agent must explain SQL before execution
- agent must not bypass SQL Guard
- agent must not execute `INSERT` or any write/destructive operation
- blocked SQL may be generated only as non-executed text with clear warning

## Schema introspection

User selected read-all schema information planning, including:

- tables
- columns
- data types
- primary keys
- foreign keys
- indexes
- views
- estimated row counts
- comments / descriptions
- constraints
- schemas / databases

Schema metadata may be returned after redaction.

## Sample rows approval

User selected:

`Sample rows are allowed only with user approval.`

Planning requirements:

- sample rows require explicit user approval
- sample rows must be limited
- sample rows must be redacted
- sample rows should not be stored in session history by default
- future allowlist / denylist support may be added later

## UI requirements

User selected all requested UI items, including:

- connection status
- DBMS type
- redacted host
- database name
- read-only status
- schema browser
- query preview
- `SELECT` execute button
- result table
- real DB warning banner
- row limit / timeout / redaction status

UI must clearly distinguish:

- sandbox DB
- mock connected DB preview
- real connected DB read-only

## Audit / session policy

User selected:

- query result rows should be shown temporarily, then disappear
- session history should record that a query was called, but should not store query result rows
- store both redacted SQL and `sql_hash`

Planning requirements:

- session history stores summary only
- audit stores redacted SQL and `sql_hash`
- audit must not store raw credentials
- driver and connection errors must be redacted

## Testing strategy

User selected:

- both fake adapter tests and optional Docker PostgreSQL/MySQL integration tests
- integration tests should skip if env vars / Docker are missing

Planning requirements:

- fake adapter tests are mandatory and always run
- Docker MySQL integration is planned first
- Docker PostgreSQL integration is planned second
- SQLite connected-file tests should use temporary path-confined files

## Release naming

User selected v1.1.0 Real Connected DB Read-only as the release naming target.

Phase 8 planning must not claim write support, destructive support, or full production DB management.
