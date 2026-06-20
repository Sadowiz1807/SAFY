# Phase 11 Driver Contracts

Phase: `Phase 11: SQL Dialect & Cloud Database Provider Expansion`  
Target release: `v1.3.0 SQL Dialect & Cloud Provider Expansion`  
Planning status: `PLANNING_COMPLETE`  
Implementation allowed: `false`

This is a planning artifact only. It does not authorize code changes, driver logic changes, SQL Guard changes, Docker service changes, test execution, cloud connections, or credential collection.

## Common Contract

Future drivers must preserve the Phase 10 driver interface patterns under `Gateway/db_drivers/` and avoid breaking SQLite, MySQL, and PostgreSQL.

Expected future files:

- `Gateway/db_drivers/sqlserver_driver.py`
- `Gateway/db_drivers/oracle_driver.py`
- `Gateway/db_drivers/provider_profiles.py`

## SQL Server Driver

- Library: `pyodbc`
- OS dependency: Microsoft ODBC Driver 18 for SQL Server
- Connection profile fields: host, port, database, username, `password_env`, encrypt, trust_server_certificate, read_only.
- Windows setup: install Microsoft ODBC Driver 18 from official Microsoft distribution; verify the driver appears as `ODBC Driver 18 for SQL Server` in ODBC Data Sources or `pyodbc.drivers()`.
- Local validation data: official Microsoft AdventureWorks sample database.

Allowed SQL:

- `SELECT`
- `WITH ... SELECT`
- metadata `SELECT` from `sys.*` and `INFORMATION_SCHEMA.*`

Blocked SQL and features:

- `EXEC`, `EXECUTE`, `sp_*`, `xp_*`, `BULK INSERT`, `SELECT INTO`, `BACKUP`, `RESTORE`
- `ALTER`, `CREATE`, `DROP`, `TRUNCATE`, `MERGE`, `UPDATE`, `DELETE`, `INSERT`
- multi-statement execution and SQL Guard bypass

## Oracle Driver

- Library: `python-oracledb`
- Mode: Thin mode first; do not require Oracle Client libraries unless Thick mode is justified later.
- Connection profile fields: host, port, service_name, username, `password_env`, read_only.
- Local/Docker validation target: Oracle Free/XE if suitable and legally/environmentally available.
- Local validation data: official Oracle Database Sample Schemas such as HR/SH or current supported package.

Allowed SQL:

- `SELECT`
- `WITH ... SELECT`
- metadata `SELECT` from `ALL_*` and `USER_*` views

Blocked SQL and features:

- `BEGIN ... END`, `DECLARE`, `EXECUTE IMMEDIATE`, `CALL`, stored procedure/function execution
- `MERGE`, `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`
- multi-statement execution and SQL Guard bypass

## Blocked Integration Rule

If SQL Server or Oracle local/Docker setup is unavailable, report `BLOCKED_SQLSERVER_VALIDATION` or `BLOCKED_ORACLE_VALIDATION`; never report fake PASS.
