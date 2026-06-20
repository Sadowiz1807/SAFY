# Phase 11 Requirements

Phase: `Phase 11: SQL Dialect & Cloud Database Provider Expansion`  
Target release: `v1.3.0 SQL Dialect & Cloud Provider Expansion`  
Planning status: `PLANNING_COMPLETE`  
Implementation allowed: `false`

This is a planning artifact only. It does not authorize code changes, driver logic changes, SQL Guard changes, Docker service changes, test execution, cloud connections, or credential collection.

## Locked Decisions

- SQL Server is a real dialect driver using `pyodbc` plus Microsoft ODBC Driver 18.
- Oracle is a real dialect driver using `python-oracledb`, Thin mode first.
- Supabase, Google Cloud SQL, and Amazon Aurora are provider/profile compatibility layers, not new SQL query-language drivers.
- Supabase maps to PostgreSQL and uses the user-provided backup for local restore validation.
- Public sample datasets are used for other local validation targets; public unauthenticated DB endpoints are not official validation targets.
- Cloud live validation is required eventually, but waits for user-provided credentials.
- Phase 10 read-only safety boundary remains locked.

## Scope

### New Real Drivers

- `sqlserver`
- `oracle`

### Provider Profiles

- `supabase` -> `postgresql`
- `google_cloud_sql` -> `mysql`, `postgresql`, `sqlserver`
- `aws_aurora` -> `mysql`, `postgresql`

## Non-Scope

- No `supabase_driver.py` unless a later non-SQL API feature proves a real need.
- No separate Cloud SQL or Aurora query-language driver.
- No write support.
- No automatic sample row fetch.
- No cloud live PASS without credentials and explicit env gates.
