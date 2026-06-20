# Phase 11 UI Spec

Phase: `Phase 11: SQL Dialect & Cloud Database Provider Expansion`  
Target release: `v1.3.0 SQL Dialect & Cloud Provider Expansion`  
Planning status: `PLANNING_COMPLETE`  
Implementation allowed: `false`

This is a planning artifact only. It does not authorize code changes, driver logic changes, SQL Guard changes, Docker service changes, test execution, cloud connections, or credential collection.

## Profile Form Changes

Extend the Phase 10 single active database profile form with provider and engine/driver selection.

Provider options:

- Self-hosted / Direct
- Supabase
- Google Cloud SQL
- Amazon Aurora

Driver / Engine options:

- SQLite
- MySQL
- PostgreSQL
- SQL Server
- Oracle

## Mapping Rules

| Provider | Allowed drivers/engines |
| --- | --- |
| Self-hosted / Direct | SQLite, MySQL, PostgreSQL, SQL Server, Oracle |
| Supabase | PostgreSQL only |
| Google Cloud SQL | MySQL, PostgreSQL, SQL Server |
| Amazon Aurora | MySQL, PostgreSQL |

The UI must prevent invalid combinations before save/test.

## Existing UX to Preserve

- Test connection
- Load schema
- Query check
- Query execute
- Schema viewer
- Result table
- Risk warning
- Blocked reason
- Safe alternative
- Timeout warning
- Retry

No sample rows are auto-fetched unless explicitly approved.

## Secret Handling

The UI stores env variable names such as `SAFY_SUPABASE_PASSWORD`, not raw secret values. Redacted placeholders may be displayed, but raw passwords must never be rendered into frontend JS or persisted profile JSON.
