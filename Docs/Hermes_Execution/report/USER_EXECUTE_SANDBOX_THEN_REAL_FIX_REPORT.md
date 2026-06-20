# SAFY User Execute: Sandbox-Then-Real Workflow Fix Report

## Scope

Implements the corrected project policy discussed with the user:

- Agent direct actions remain read-only guarded.
- User Execute Box actions are user-controlled.
- Pressing `Check Safety` validates SQL in sandbox.
- Pressing `Execute` runs the sandbox-validated SQL against the real connected database.
- No separate `Run in Sandbox` button is required.
- Save Database reports whether the sandbox was created, started, already ready, not ready, or failed.

## Main behavior change

### Before

`/query/check` with:

```json
{
  "target": "connected_database",
  "real_db_mode": true
}
```

used the real DB read-only policy directly. Therefore DDL/DML like `CREATE TABLE` was blocked before sandbox validation.

### After

The public `/query/check` endpoint is treated as the user Execute Box workflow:

```text
Check Safety
→ validate SQL in sandbox
→ if sandbox passes, return allowed_to_attempt=true
→ store a check_id that permits real connected DB execution
```

`/query/execute` then runs against the connected database only if:

- check_id exists
- sql_hash matches
- sandbox validation passed
- user_decision is yes
- database_profile_id matches

## Agent safety preserved

Internal skill/agent checks still use `execution_path="skill_query_guard"` and are not routed through this user Execute Box bypass. Agent direct write/DDL is still blocked by read-only guard.

## Sandbox validation

Added:

```text
SandboxManager.execute_validation()
```

For PostgreSQL sandbox:
- Runs SQL as `safy_owner`.
- Wraps SQL in `BEGIN; ... ROLLBACK;`.
- Validates DDL/DML/SELECT without permanently mutating sandbox.

For SQLite sandbox:
- Uses transaction + rollback.

Unsupported sandbox engines return a clear staged follow-up error.

## Real DB user execution

Added user-controlled real execution support:

```text
Gateway/db_drivers/factory.py::execute_user_sql()
```

Implemented for:

- PostgreSQL
- MySQL
- SQLite

Supabase REST behavior:

- SELECT still uses the existing REST read-only path.
- DDL/DML returns `SUPABASE_REST_WRITE_UNSUPPORTED` because PostgREST cannot execute arbitrary SQL like `CREATE TABLE`.

This is no longer reported as a read-only policy block. It is a driver capability limitation.

## Save Database sandbox messages

Save Database response now includes detailed sandbox status:

- `sandbox_created`
- `sandbox_started`
- `sandbox_already_ready`
- `sandbox_not_ready`
- `sandbox_failed`

UI now displays the returned `sandbox_message`.

Examples:

```text
Database saved. Sandbox created and ready.
Database saved. Sandbox already ready.
Database saved, but sandbox is failed.
```

## Files changed

- `Apps/Web/safy-ui.js`
- `Apps/Api/safy_api/main.py`
- `Gateway/query_orchestrator.py`
- `Sandbox/sandbox_manager.py`
- `Gateway/db_drivers/base.py`
- `Gateway/db_drivers/factory.py`
- `Gateway/db_drivers/postgres_driver.py`
- `Gateway/db_drivers/mysql_driver.py`
- `Gateway/db_drivers/sqlite_driver.py`
- `Gateway/db_drivers/supabase_rest_driver.py`

## Important note for Supabase REST

If your active database profile uses Supabase REST `/rest/v1`, SAFY can test connection and execute simple SELECT queries through PostgREST.

It cannot execute:

```sql
CREATE TABLE ...
ALTER TABLE ...
DROP TABLE ...
INSERT ...
UPDATE ...
DELETE ...
```

against the real Supabase database through REST.

To execute real DDL/DML on Supabase, create a direct PostgreSQL connection profile or add a controlled SQL RPC function and implement that driver path.

## Verification

Executed:

```bash
node --check Apps/Web/safy-ui.js
python -m py_compile Apps/Api/safy_api/main.py Apps/Api/safy_api/schemas.py Gateway/query_orchestrator.py Sandbox/sandbox_manager.py Gateway/db_drivers/base.py Gateway/db_drivers/factory.py Gateway/db_drivers/postgres_driver.py Gateway/db_drivers/mysql_driver.py Gateway/db_drivers/sqlite_driver.py Gateway/db_drivers/supabase_rest_driver.py Agent/agent_runtime.py Skills/*/runtime.py
```

Result: PASS.

## Final status

SAFY_USER_EXECUTE_SANDBOX_THEN_REAL_FIXED
