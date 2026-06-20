# SAFY Schema Window + Execute Connection Fix Report

## Scope

Fixes two issues reported after the skills/schema graph pass:

1. Schema Graph was embedded in the dashboard/right sidebar.
2. Query execution could show a misleading database connection failure even when Test Connection passed.

## UI fix

Schema Graph is now a separate modal-style window.

Changed:

- Removed the embedded Schema Graph panel from the dashboard right sidebar.
- Added an `Open Schema Graph` button.
- Added a separate `schema-graph-window` overlay outside the dashboard shell.
- Existing Refresh/Delete/Reset actions remain inside the separate window.

## Execution fix

### Backend

`/query/execute` now re-materializes the checked active database profile from backend storage before calling the driver.

This keeps execution consistent with Test Connection and Check Safety when API keys are stored in `.env`.

### Supabase REST driver

Supabase REST HTTP errors are no longer collapsed into generic connection failure:

- HTTP 401/403 → `DB_AUTH_FAILED`
- HTTP 404 → `DB_RESOURCE_NOT_FOUND`
- Other HTTP errors → `DB_REQUEST_FAILED`

### Frontend error copy

Execution/table/query errors no longer display as generic `Database connection failed`.

Now they tell the user to refresh Schema Graph, regenerate SQL, or edit table name when the table/endpoint is not found.

## Important note

A valid Test Connection only proves the Supabase REST base endpoint and API key are reachable.

A generated query can still fail if:

- the generated table name does not exist,
- Supabase REST cannot execute the SQL shape,
- the query is not a simple SELECT supported by PostgREST.

This fix prevents those cases from being mislabeled as base connection failure.

## Files changed

- `Apps/Web/index.html`
- `Apps/Web/styles.css`
- `Apps/Web/safy-ui.js`
- `Apps/Api/safy_api/main.py`
- `Gateway/db_drivers/supabase_rest_driver.py`

## Verification

Executed:

```bash
node --check Apps/Web/safy-ui.js
python -m py_compile Apps/Api/safy_api/main.py Apps/Api/safy_api/schemas.py Gateway/db_drivers/supabase_rest_driver.py Gateway/query_orchestrator.py Agent/agent_runtime.py Skills/*/runtime.py
```

Result: PASS.

## Final status

SAFY_SCHEMA_WINDOW_AND_EXECUTE_CONNECTION_FIXED
