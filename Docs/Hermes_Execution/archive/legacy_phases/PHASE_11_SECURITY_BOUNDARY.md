# Phase 11 Security Boundary

Phase: `Phase 11: SQL Dialect & Cloud Database Provider Expansion`  
Target release: `v1.3.0 SQL Dialect & Cloud Provider Expansion`  
Planning status: `PLANNING_COMPLETE`  
Implementation allowed: `false`

This is a planning artifact only. It does not authorize code changes, driver logic changes, SQL Guard changes, Docker service changes, test execution, cloud connections, or credential collection.

## Locked Boundary

Phase 11 must preserve the Phase 10 read-only boundary for all dialects and provider profiles.

## Globally Blocked

- `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `REPLACE`, `MERGE`
- `CALL`, `EXEC`, `EXECUTE`, stored procedure execution
- `GRANT`, `REVOKE`, `LOAD DATA`, `COPY`, `BULK INSERT`, `SELECT INTO`
- DDL, database writes, multi-statement execution, SQL Guard bypass
- `/query/check` database connection or SQL execution
- raw password persistence, raw DSN persistence, raw SQL persistence by default
- query result row persistence
- traceback leakage to UI/API by default

## Allowed Read-Only Baseline

- `SELECT`
- `WITH ... SELECT`
- `SHOW` / `DESCRIBE` where supported
- `EXPLAIN SELECT` where supported

Dialect-specific metadata inspection belongs in schema/profile endpoints, not `/query/check` execution.

## SQL Server Extra Blocks

- `EXEC`, `EXECUTE`, `sp_*`, `xp_*`, `BULK INSERT`, `SELECT INTO`, `BACKUP`, `RESTORE`

SQL Server metadata may query `sys.tables`, `sys.columns`, `sys.schemas`, `sys.indexes`, and `INFORMATION_SCHEMA.*`.

## Oracle Extra Blocks

- `BEGIN ... END`, `DECLARE`, `EXECUTE IMMEDIATE`, `CALL`, procedure/function execution

Oracle metadata may query `ALL_TABLES`, `ALL_TAB_COLUMNS`, `ALL_CONSTRAINTS`, `ALL_INDEXES`, `USER_TABLES`, and `USER_TAB_COLUMNS`.
