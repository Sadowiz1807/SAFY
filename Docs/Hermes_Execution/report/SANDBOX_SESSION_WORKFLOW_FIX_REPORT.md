# SAFY Sandbox + Session Workflow Fix Report

## Scope

Fixes the issues shown in the user screenshot:

1. Save/Test database reported `Sandbox not_ready: SUPABASE_REST_SCHEMA_CACHE_NOT_IMPLEMENTED`.
2. Docker was available but SAFY did not create/start a usable sandbox after saving a Supabase REST database.
3. Selecting an old chat session did not reload the conversation.
4. Schema Graph should open as a separate window, not be embedded in the dashboard.

## Fix 1: sandbox creation after Save Database

Updated `Apps/Api/safy_api/main.py`.

### Before

Supabase REST profiles were forced into:

```text
sandbox_status = not_ready
SUPABASE_REST_SCHEMA_CACHE_NOT_IMPLEMENTED
```

even when Docker was available.

### After

- Save Database still tests the connected DB first.
- Then backend creates/starts a sandbox.
- For Supabase REST profiles, SAFY creates a real PostgreSQL sandbox engine because there is no local REST sandbox runtime.
- Sandbox status now reflects the actual sandbox manager result.
- The old forced `SUPABASE_REST_SCHEMA_CACHE_NOT_IMPLEMENTED` not-ready response is removed.

## Fix 2: existing sandbox start

If a sandbox already exists for the database profile but is not ready, SAFY now attempts to start it again instead of simply returning stale state.

## Fix 3: session persistence

Updated `/agent/chat` in `Apps/Api/safy_api/main.py`.

### Before

Chat UI created sessions, but `/agent/chat` did not persist user/assistant messages into the runtime DB.

### After

For every chat:

- Backend ensures the session exists.
- User message is saved.
- Assistant response is saved with structured metadata.
- Old sessions can be loaded from `/sessions/{chat_id}/messages`.

## Fix 4: session restore UI

Updated `Apps/Web/safy-ui.js`.

- Session metadata parsing is now safe.
- Old sessions render user/assistant messages.
- Latest generated SQL from history is restored into the Execute Box.
- Active session highlighting still works.

## Fix 5: Schema Graph separate window

Schema Graph is now opened by `Open Schema Graph` and rendered in a separate modal-style window.

## Fix 6: clearer execute errors

Supabase REST runtime errors are no longer collapsed into generic connection failure.

- `DB_AUTH_FAILED` → auth/API key issue
- `DB_RESOURCE_NOT_FOUND` → table/endpoint not found
- `SUPABASE_REST_SQL_UNSUPPORTED` → generated SQL shape is unsupported by REST driver

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
python -m py_compile Apps/Api/safy_api/main.py Apps/Api/safy_api/schemas.py Gateway/db_drivers/supabase_rest_driver.py Gateway/query_orchestrator.py Agent/agent_runtime.py Sandbox/sandbox_manager.py Skills/*/runtime.py
```

Result: PASS.

## Final status

SAFY_SANDBOX_SESSION_WORKFLOW_FIXED
