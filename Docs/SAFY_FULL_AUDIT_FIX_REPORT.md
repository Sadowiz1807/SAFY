# SAFY Full Project Audit and Fix Report

**Audit target:** uploaded `SAFY(15).zip` snapshot  
**Audit date:** 2026-06-24  
**Scope:** source review, safety-policy review, privacy review, unit tests, static parsing, packaging/import smoke test, and local HTTP health smoke test.

## 1. Safety rules applied

The fixes preserve these project rules:

1. Agent-direct access to a connected real database remains read-only.
2. User-controlled DDL/DML from Execute Box must pass isolated sandbox validation before real execution.
3. Real execution requires the same `check_id`, SQL hash, target, database profile, and explicit user action.
4. `DROP`, `TRUNCATE`, privilege changes, account/server administration, executable database code, and row-level-security changes remain blocked pending a separate administrative workflow.
5. PostgreSQL native connections and Supabase API/RPC profiles remain separate execution paths.
6. Secrets, raw provider responses, result rows, and sensitive SQL literals must not enter audit/session state.
7. Because more than six files were changed, delivery is the cleaned full project rather than a patch-only package.

## 2. Primary regression fixed

### User `CREATE TABLE` was blocked before sandbox validation

The Execute Box policy now distinguishes ordinary user-approved DDL from agent-direct execution:

- `CREATE TABLE`, normal schema DDL, and supported DML can reach sandbox validation when the saved profile uses `credential_permissions`.
- A successful sandbox check returns `ALLOW_AFTER_SANDBOX` and enables the explicit Execute boundary.
- Agent-direct real-database execution remains read-only.
- The UI no longer recommends reconnecting the database for a generic `SQL_POLICY_BLOCKED` result. Reconnect/repair guidance is limited to actual sandbox/profile readiness errors.

Markdown-fenced SQL such as a single ` ```sql ... ``` ` block is safely unwrapped before classification. Prose around a fence or multiple statements still fails closed.

## 3. Additional defects fixed

### Query safety and execution integrity

- Enforced saved database profile permissions as authoritative; request payloads cannot escalate `read_only` or `disabled` profiles to `credential_permissions`.
- Blocked transaction-control statements in Execute Box.
- Kept `DROP` and `TRUNCATE` blocked.
- Added classification for security-sensitive DDL, including user/role/login/database administration, functions/procedures, policies, row-level-security changes, trigger enable/disable, ownership changes, and security-definer/invoker clauses.
- Serialized one-time check execution to prevent concurrent double execution.
- Consumed a mutation check before contacting the real database after audit prewrite. This prevents replay when a driver/network error occurs after an ambiguous server-side commit.
- Added failed-attempt audit records without SQL text or provider payloads.
- Removed fake-driver write execution; fake profiles now fail explicitly instead of returning a failure-shaped payload that could be mistaken for success.
- Corrected schema invalidation so INSERT/UPDATE/DELETE do not unnecessarily invalidate schema snapshots; actual schema mutations still do.
- Removed cancelled checks and confirmation state.
- Added strict API row-limit validation (`1..1000`) and driver-level clamping for internal callers.

### Database routing and Supabase safety

- Kept native Supabase PostgreSQL profiles on the PostgreSQL driver.
- Kept Supabase API profiles on the separate `supabase_rpc` path using `safy_execute_sql` for approved writes.
- Removed arbitrary provider/RPC response bodies from execution metadata and error persistence.
- Replaced unsafe substring validation of Supabase URLs with parsed HTTPS hostname validation. URLs such as `project.supabase.co.attacker.example` are rejected before an API key can be sent.

### Sandbox correctness

- SQLite DDL/DML validation now uses an explicit transaction and rollback; `executescript()` is not used because it can implicitly commit.
- SQLite restore sources are confined to managed/explicitly allowed roots.
- Restore accepts only regular files and verifies SQLite backups before copying.
- Added configurable restore-size limits and bounded gzip decompression to prevent archive expansion from exhausting disk space.
- SQLite schema introspection now safely quotes unusual table names.
- PostgreSQL sandboxes no longer report `ready` when no Docker runtime exists.
- Docker is used when available even if the CI Docker gate is optional; without Docker, PostgreSQL sandbox startup fails honestly with `SANDBOX_DOCKER_REQUIRED_FOR_POSTGRES`.

### Privacy and persistence

- Removed SQL text recursively from audit metadata.
- Removed nested result rows and provider response payloads from SQLite and JSON runtime state.
- Sanitized schema-snapshot and workspace-lock metadata at the storage boundary.
- Execution memory stores only compact status, row count, action class, audit ID, and schema-change facts.
- Sensitive SQL literals are redacted when SQL references credential-like fields.
- Added recursive sandbox-audit sanitation.
- Fixed JSON session filename collisions for IDs such as `team/chat` and `team_chat`.
- Fixed schema-graph filename collisions and excessive filename length for transformed/long profile IDs.

### Packaging and runtime

- Corrected package discovery so editable install includes required namespace packages.
- Added pytest configuration for project imports.
- Removed BOM from the example profile JSON.
- Verified CLI import and launch from outside the repository working directory.

## 4. Validation evidence

Completed successfully:

- `pytest -q`: **43 passed**
- Python compile scan across application, gateway, state, sandbox, tests, and scripts: passed
- JavaScript syntax check for `Apps/Web/safy-ui.js`: passed
- Skill registry validation: passed, **11 skills**, canonical skill `text_to_sql`
- JSON parse scan: **478 files**, 0 errors
- YAML parse scan: **20 files**, 0 errors
- Editable package install (`pip install -e . --no-deps`): passed
- External import smoke test from `/tmp`: passed
- CLI `safy info`: passed
- Local server launch and `GET /health`: HTTP 200, SAFY status `ok`

## 5. Environment-limited checks

The following could not be certified in this container:

- Docker-backed PostgreSQL sandbox integration, because Docker is not installed.
- Live PostgreSQL/MySQL/SQL Server/Oracle/Supabase execution, because no external test endpoints or credentials were provided.
- Gitleaks/Bandit/Ruff scans, because those executables are not installed. A custom secret/path/static scan is performed on the clean delivery package instead.

`pip check` reported one unrelated global-environment conflict: installed `moviepy 2.2.1` requires Pillow `<12`, while the container has Pillow `12.2.0`. SAFY does not declare or use MoviePy in its project requirements, so this is not treated as a SAFY dependency defect.

## 6. Delivery sanitation

The delivered full-project archive excludes:

- `.git`, `.env`, caches, compiled Python files, build artifacts, and egg metadata
- runtime database/profile/session/sandbox/audit files
- `Data/secrets`
- generated schema-graph state
- local logs and temporary files

Example/template configuration files remain included.
