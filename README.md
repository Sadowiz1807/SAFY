# SAFY

SAFY is an AI-assisted database agent and database safety gateway for schema inspection, SQL checking, and read-only query execution. It is designed to put SQL Guard, confirmation gates, redaction, audit metadata, and state-bound execution between users/agents and database access.


## Current Canonical Status

The canonical project-status and audit baseline is now maintained at:

```text
Docs/SAFY_CURRENT_PROJECT_STATUS.md
```

That document is the source of truth for the current SAFY architecture, safety matrix, sandbox workflow, compatibility status, test matrix, and next phases. Older stage/phase notes in this README and under `Docs/Hermes_Execution/` are historical unless explicitly referenced by the current-status document.

## Current Version

SAFY is currently past the legacy `v1.3.0 SQL Dialect & Cloud Provider Expansion` notes. The active baseline is the Hermes-inspired workflow restructure described in `Docs/SAFY_CURRENT_PROJECT_STATUS.md`. SAFY supports direct read-only database access, sandbox-first write/DDL review, deterministic SQL policy/reviewer checks, and runtime/audit trace boundaries. SAFY is still not an unrestricted production database administration tool.

SAFY v1.3.0 supports read-only SQLite/MySQL/PostgreSQL plus Database services SQL Server and Oracle driver contracts. Supabase, Google Cloud SQL, and Amazon Aurora are provider profiles over underlying SQL dialect drivers, not separate query-language drivers. Docker-backed SQL Server/Oracle local integration passed in the env-gated real run after starting the Database services containers.

## Supported Features

- FastAPI backend for profiles, query checks, query execution, sessions, and agent chat.
- Static web UI under `Apps/Web`.
- SQL Guard / query check before execution.
- State-bound `/query/execute` that requires a valid checked state.
- Sandbox test-support compatibility from earlier milestones.
- Real connected DB read-only profile flow.
- Schema introspection for connected databases.
- Real read-only `SELECT` execution when allowed.
- Sensitive or broad `SELECT` confirmation.
- Write/DDL draft handling through Execute Box, sandbox validation, and explicit Execute-button confirmation.
- Blocked operation handling for destructive SQL, unsafe SQL, unknown SQL, and broad mutations.
- Temporary result display without result-row persistence in session history.
- Audit/session metadata with redacted SQL and hashes rather than raw result rows.
- Redaction and secret-handling boundaries for credentials, driver errors, UI output, logs, reports, and audit records.
- Runtime test suite covering fake-adapter validation, read-only execution, blocked writes, profile secret handling, API surfaces, and UI labels.

## Database Support

Priority and support order:

1. MySQL
2. PostgreSQL
3. SQLite
4. SQL Server
5. Oracle

MySQL/PostgreSQL/SQLite remain Runtime test baseline drivers. Database services adds SQL Server and Oracle as real SQL dialect drivers. These adapters may require optional driver dependencies, OS client drivers, and environment configuration before use in a local or Docker-backed real database environment. Optional Docker integration tests are environment-gated and should skip when Docker, drivers, or required environment variables are unavailable.

SQLite connected-file mode must be path-confined and opened read-only.

Supabase, Google Cloud SQL, and Amazon Aurora are provider profiles over underlying SQL dialect drivers. They do not bypass SQL Guard and are not independent query languages.

## Read-only Safety Boundary

Allowed in real connected DB mode:

- `SELECT`
- schema introspection
- safe metadata queries
- optional safe `EXPLAIN` if supported by the adapter and guaranteed read-only

Not direct-run in real connected DB chat mode:

- `INSERT`
- `UPDATE`
- `DELETE`
- `CREATE`
- `ALTER`
- schema/data mutation SQL

These statements must be drafted into Execute Box, pass sandbox validation, and be explicitly executed by the user.

Blocked by default or requiring a separate administrative workflow:

- `DROP`
- `TRUNCATE`
- `GRANT`
- `REVOKE`
- server/security/admin statements
- multi-statement SQL
- `SELECT ... FOR UPDATE`
- side-effect functions or any SQL that changes permissions, server state, or locks rows for mutation

## Query Workflow

User SQL textbox workflow:

```text
User enters SQL -> /query/check -> SQL Guard -> confirmation if needed -> /query/execute -> temporary result display
```

Agent workflow:

```text
Agent inspects schema -> generates SQL -> explains SQL -> /query/check -> confirmation if needed -> /query/execute for allowed read-only SELECT only
```

Blocked SQL workflow:

```text
Blocked SQL may be displayed as non-executed text with a warning, but SAFY will not run it.
```

`/query/check` must not execute SQL. `/query/execute` requires a valid checked state. Sensitive or broad `SELECT` statements may require confirmation before execution.


## Stage 9 JSON Storage Target

Stage 9 targets canonical JSON storage at:

```text
Data/safy_profiles.json
Data/sessions/session_<id>.json
Data/audit/safy_audit.jsonl
```

The current correction pass completes Pass 1 hardening and records Pass 2 as continuation-required unless those canonical profile, session, and audit paths are fully implemented and tested. `Data/sessions/runtime` is not the final semantic storage layout. Stage 9 does not create database drivers, does not enable write support, and does not enable `INSERT`; write and `INSERT` operations remain blocked.

## Credential Handling

- Local `.env` credentials are allowed for developer/local use.
- Database profiles should store environment variable names and metadata only.
- Raw passwords must not be stored in JSON profile stores, runtime DB, audit records, session history, UI output, logs, reports, or test snapshots.
- Transient UI/API password input may be used for connection testing or one-time session use, but it must not be persisted.
- Driver errors and connection failures must be redacted before reaching users, logs, audit records, reports, or UI output.
- Use fake placeholders in examples and documentation.

## Example `.env`

```env
SAFY_MYSQL_HOST=localhost
SAFY_MYSQL_PORT=3306
SAFY_MYSQL_DATABASE=safy_demo
SAFY_MYSQL_USERNAME=safy_readonly
SAFY_MYSQL_PASSWORD=change-me-fake

SAFY_POSTGRES_HOST=localhost
SAFY_POSTGRES_PORT=5432
SAFY_POSTGRES_DATABASE=safy_demo
SAFY_POSTGRES_USERNAME=safy_readonly
SAFY_POSTGRES_PASSWORD=change-me-fake
```

Use a database user with read-only permissions for real connected DB profiles.

## Database services Docker Integration Targets

Database services includes optional local Docker automation for SQL Server and Oracle integration targets:

```powershell
Copy-Item Docker\.env.database_services.example Docker\.env.database_services
Scripts\check_database_services_docker.ps1 -RequireSqlServerOdbc
Scripts\start_database_services_databases.ps1 -Wait
```

The Docker layer creates local seed schemas and a `safy_readonly` user for validation only. It does not enable SAFY write support. SQL Server uses a small local seed schema by default because AdventureWorks restore is heavier; Oracle uses a small local seed schema by default because full Oracle Sample Schemas setup can be heavy.

Run env-gated integration tests only after containers are healthy and local test passwords are set:

```powershell
$env:SAFY_STAGE11_SQLSERVER_DOCKER_REQUIRED="1"
$env:SAFY_STAGE11_ORACLE_DOCKER_REQUIRED="1"
$env:SAFY_SQLSERVER_PASSWORD="safy_ro_database_services_fake_123!"
$env:SAFY_ORACLE_PASSWORD="safy_ro_database_services_fake_123"
python -m pytest Tests\database_services -q -rs --ignore=tmp --basetemp=tmp\pytest_database_services
```

If Docker Desktop is not running, report `BLOCKED_DOCKER_ENGINE_NOT_RUNNING`. If Microsoft ODBC Driver 18 is missing, report `SQLSERVER_ODBC_DRIVER_MISSING`. If SQL Server sqlcmd is missing in the container, report `BLOCKED_SQLSERVER_SQLCMD_MISSING`. If the SQL Server readonly login smoke test cannot open `safy_database_services`, report `BLOCKED_SQLSERVER_LOGIN_MAPPING` and do not claim PASS. If Oracle image/setup is unavailable, report `BLOCKED_ORACLE_VALIDATION`. The latest env-gated local Docker run passed for both SQL Server and Oracle.

Stop local targets with:

```powershell
Scripts\stop_database_services_databases.ps1
```

## Installing And Running

From the repository root, install the editable console launcher:

```powershell
python -m pip install -e .
```

Start SAFY and open the dashboard after `/health` is ready:

```powershell
safy run
```

Start SAFY without opening a browser:

```powershell
safy run --no-browser
```

If Windows does not recognize bare `safy` from `C:\Users\ASUS`, Python's Scripts directory is not on `PATH`. Run `Scripts/install_safy_launcher.ps1` or add the directory printed by that helper to `PATH`, then retry `safy info` and `safy run --no-browser`. Do not treat bare `safy run` as validated until it works from `C:\Users\ASUS` in that shell.

The FastAPI application is defined in `Apps/Api/safy_api/main.py`. The dashboard is served at `/`; static assets are served from `/static`; `/docs` is the developer OpenAPI UI; `/health` returns the readiness envelope used by the launcher.

## Opening The Web UI

Static UI files are located at:

```text
Apps/Web/index.html
Apps/Web/styles.css
Apps/Web/safy-ui.js
```

Use `http://127.0.0.1:8000/` after `safy run`; do not open `Apps/Web/index.html` directly for Stage 9 validation because the API-served dashboard owns the `/static/...` asset paths.

## Basic Usage

1. Start the backend.
2. Open the UI.
3. Create or select a database profile.
4. Test the connection.
5. Inspect schema metadata.
6. Enter a `SELECT` query.
7. Review the `/query/check` result.
8. Confirm if the query is sensitive or broad.
9. Execute through `/query/execute`.
10. View temporary results and row-limit/timeout/redaction status.

## API Endpoint Overview

Key endpoints implemented or extended by Runtime:

```text
POST /profiles/database/save
POST /profiles/database/test
GET  /profiles/database/{database_profile_id}/status
GET  /profiles/database/{database_profile_id}/schema
POST /query/check
POST /query/execute
POST /agent/chat
```

All real DB query execution must pass through the query-check and state-bound execute flow.

## Testing

Run Runtime tests:

```powershell
python -m pytest Tests/runtime -q
```

Run the full API contract-8 suite:

```powershell
python -m pytest Tests/api_contract Tests/api_contract_5 Tests/stage2 Tests/stage2_5 Tests/sql_guard Tests/agent_runtime Tests/agent_runtime_5 Tests/api_runtime Tests/stage6 Tests/stage7 Tests/runtime -q --basetemp=tmp/pytest_runtime_final
```

Run static checks:

```powershell
python -m compileall .
node --check Apps/Web/safy-ui.js
```

Latest confirmed Runtime validation evidence recorded in `Docs/Hermes_Execution/report/RUNTIME_IMPLEMENTATION_REPORT.md` and `Docs/Hermes_Execution/report/RUNTIME_FINAL_REPORT.md` includes `158 passed` for the API contract-8 suite.

## Optional Integration Tests

- Test-support adapter tests are mandatory and always run.
- Docker MySQL integration tests are optional and environment-gated.
- Docker PostgreSQL integration tests are optional and environment-gated.
- SQLite path-confined integration can use temporary read-only database files.
- Optional tests should skip if Docker, required environment variables, database drivers, or local DB services are missing.

## Troubleshooting

Common issues and stable error codes:

- `DB_PROFILE_NOT_FOUND` - selected database profile does not exist.
- `DB_CONNECTION_FAILED` - database connection failed with a redacted error.
- `DB_AUTH_FAILED` - authentication failed; check read-only user credentials and env vars.
- `DB_SSL_REQUIRED` - database requires SSL configuration.
- `DB_TIMEOUT` - connection, schema introspection, or query execution timed out.
- `DB_READONLY_VIOLATION` - SQL violates read-only mode, such as `SELECT ... FOR UPDATE`.
- `DB_UNSAFE_SQL_BLOCKED` - SQL is unsafe or changes data/schema/permissions/server state.
- `DB_SCHEMA_INTROSPECTION_FAILED` - schema read failed with a redacted error.
- `DB_RESULT_LIMIT_EXCEEDED` - query exceeded configured row/result limits.
- `DB_SAMPLE_ROWS_APPROVAL_REQUIRED` - sample rows require explicit approval.
- `DB_SENSITIVE_SELECT_CONFIRMATION_REQUIRED` - sensitive or broad `SELECT` requires confirmation.
- `DB_DRIVER_ERROR_REDACTED` - raw driver error was redacted.
- `DB_INSERT_BLOCKED` - `INSERT` is blocked in Runtime read-only mode.

## Project Structure

```text
Apps/Api                FastAPI backend
Apps/Web                Static web UI
Core                    Agent core and execution context
Gateway                 SQL guard, query orchestration, adapters, real DB policy
DataStore               Profile storage and validation
State                   Runtime/session state
Audit                   Audit store and audit logger
Logging                 Redaction helpers
Tests                   Stage test suites
Docs/Hermes_Execution   Stage plans, contracts, reports, and validation docs
```

## Security Notes

- No raw secret persistence.
- No result-row persistence in session history.
- SQL Guard is mandatory for query execution.
- `/query/execute` is state-bound to a prior check.
- Driver errors and tracebacks are redacted.
- A read-only database user is recommended for every real connected DB profile.
- Agent execution cannot bypass SQL Guard or execute blocked SQL.

## Roadmap / Future Updates

This `README.md` is the main project README and should be updated after future stages.

Future write support, if ever added, must be a separately approved gated stage. Do not silently add write support. Cloud DB support, SSH tunnel/proxy/VPN support, managed provider hardening, broader dependency packaging, and production hardening may be future scope.

## Final Warning

SAFY v1.1.0 is read-only for real connected databases. It is not a tool for executing writes, migrations, destructive SQL, or unrestricted production database administration.




## Runtime test Reconciled Validation Status

Runtime test supports read-only SQLite/MySQL/PostgreSQL drivers. MySQL/PostgreSQL validation requires Docker. The latest Runtime test Docker validation passed with `SAFY_STAGE10_DOCKER_REQUIRED=1`.

User-provided validation evidence recorded during final report reconciliation:

- `SAFY_STAGE10_DOCKER_REQUIRED=1` was enabled.
- `Tests/runtime_test` was rerun after Docker became available.
- Result: 9 passed, 0 skipped.
- MySQL Docker validation: PASS.
- PostgreSQL Docker validation: PASS.
- SQLite local validation: PASS.
- Full regression was previously observed as 183 passed, 2 skipped. The 2 skipped tests in the full suite are not Runtime test Docker validations, because Runtime test Docker validation was rerun separately and passed with 9 passed, 0 skipped.

Initial validation attempt was blocked because Docker Desktop/Linux engine was unavailable. After Docker became available and `SAFY_STAGE10_DOCKER_REQUIRED=1` was set, Runtime test Docker validation was rerun and passed with 9 passed, 0 skipped.

Safety status remains unchanged: read-only only, no INSERT, no UPDATE/DELETE/DDL, no raw password persistence, no result row persistence, and no SQL Guard bypass.

## Runtime test: v1.2.0 Real DB Driver Read-only

Runtime test adds real read-only drivers for MySQL, PostgreSQL, and SQLite behind SAFY SQL Guard. Install optional dependencies with:

```powershell
python -m pip install -r requirements-db.txt
```

Docker test databases use:

```powershell
docker compose -f Docker/docker-compose.runtime_test.yml up -d
$env:SAFY_STAGE10_DOCKER_REQUIRED = "1"
$env:SAFY_STAGE10_MYSQL_PASSWORD = "safy_ro_runtime_test"
$env:SAFY_STAGE10_POSTGRES_PASSWORD = "safy_ro_runtime_test"
python -m pytest Tests/runtime_test -q --ignore=tmp --basetemp=tmp\pytest_runtime_test_docker
docker compose -f Docker/docker-compose.runtime_test.yml down -v
```

Database profiles store metadata in `Data/safy_profiles.json`; set `password_mode` to `env` and store only `password_env`, never raw password values or DSNs with credentials. Recommended production setup is a database user with SELECT-only grants.

UI workflow: open the dashboard, configure the single active database profile, test connection, load schema, write a SELECT, run `/query/check`, then execute through `/query/execute`. Agent auto-SELECT is allowed only through the same guarded check/execute path and only for read-only SQL bound to the active profile.

Blocked operations include INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, REPLACE, MERGE, CALL, EXEC, GRANT, REVOKE, LOAD DATA, COPY, DDL, multi-statement SQL, and locking SELECTs. Query rows are temporary response data only; session and audit records store metadata such as driver, database profile id, SQL hash, row count, status, and redacted error fields.

Troubleshooting: if Docker validation fails with a Docker API or Linux engine error, start Docker Desktop and rerun the compose command. If connection tests fail, verify the readonly user grants and the `SAFY_STAGE10_*_PASSWORD` environment variables.
