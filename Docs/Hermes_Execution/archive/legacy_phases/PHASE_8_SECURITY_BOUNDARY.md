# Phase 8 Security Boundary

Executed by main-agent only. No sub-agents used.

## Core boundary

Phase 8 permits real DB read-only behavior only.

Phase 8 must enforce all of the following:

- real DB read-only only
- real DB write / destructive operations blocked
- INSERT is blocked in Phase 8
- credentials cannot be persisted raw
- transient secrets must be redacted and not logged
- SQL Guard mandatory
- `/query/check` must not execute SQL
- `/query/execute` must require valid check binding
- sensitive SELECT requires confirmation
- sample rows require approval
- result rows are not stored in session history
- audit stores redacted SQL + `sql_hash`
- driver errors are redacted
- agent cannot bypass SQL Guard
- agent cannot execute blocked SQL
- blocked SQL can be displayed as non-executed text with warning

## Allowed operations

Allowed operations are limited to:

- schema introspection
- safe metadata queries
- read-only `SELECT`
- optional `EXPLAIN` only if a DBMS-specific implementation proves it is guaranteed read-only and remains behind SQL Guard policy

## Blocked operations

Blocked operations include:

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
- `CALL`
- stored procedures
- multi-statement SQL
- `SELECT ... FOR UPDATE`
- side-effect functions
- SQL that mutates data, schema, permissions, server state, or row locks

## Credential boundary

Credential rules:

- profile JSON may store env var names or other non-secret metadata only
- raw password entry may exist only as transient request-scoped or session-scoped input
- runtime DB must not persist raw credentials
- audit must not persist raw credentials
- UI must not display raw credentials
- reports, test snapshots, and logs must not contain raw credentials

## Query-check boundary

`/query/check` is a policy gate only.

It must:

- classify SQL
- enforce read-only rules
- detect blocked mutation/destructive SQL
- detect sensitive or broad read patterns
- return confirmation requirements when necessary
- never execute SQL

## Execute boundary

`/query/execute` may run only when:

- a valid check exists
- `sql_hash` matches
- target/profile binding matches
- the check is not expired or consumed
- required confirmation has been satisfied
- SQL remains within read-only policy

## Agent boundary

The agent may:

- inspect real schema
- generate SQL for the existing schema
- explain SQL
- execute allowed read-only SELECT through the same guarded path as the user workflow

The agent may not:

- bypass SQL Guard
- bypass confirmation rules
- execute INSERT or any blocked SQL
- open a write-capable execution path in Phase 8

## Audit and session boundary

Audit may store:

- DB profile ID
- DBMS type
- `sql_hash`
- redacted SQL or summary
- row count
- truncation flag
- execution time
- audit ID
- timestamp

Session history must not store result rows.

Real result rows may be shown temporarily in UI, then cleared.

## Error boundary

All DB and driver failures must be normalized and redacted.

UI and API responses must not expose:

- raw tracebacks
- raw connection strings
- raw driver diagnostics containing secrets
- raw credentials

## Phase 8 Must Not Weaken

Phase 8 must not weaken any existing SAFY safety properties from earlier phases, including:

- no raw secret persistence
- no agent bypass around SQL Guard
- no hidden real DB execution path
- no mutation support disguised as preview or explain
- no session-history persistence of sensitive result payloads
- no ambiguity about INSERT: it is blocked in Phase 8

## Release boundary

Even after implementation, Phase 8 supports only `v1.1.0 Real Connected DB Read-only`.

It must not be described as:

- real connected DB write MVP
- destructive DB admin support
- unrestricted production DB management
