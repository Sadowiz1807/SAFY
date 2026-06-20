# SAFY Schema Graph + Text-to-Query Workflow Fix Report

## Scope

This pass implements the agreed active-database schema graph workflow and makes `/Execute` generate SQL using the active database context.

The package contains only new/changed files.

## Implemented behavior

### Active database only

- SAFY now treats one database as active at a time.
- Chat/query execution does not parse database names from user prompts.
- `/Execute` uses the active database profile supplied by the UI/backend.

### Switch Database UI

Added a switch control in Database Management:

- It lists saved database profiles from the backend.
- Switching activates one database profile.
- After switch, the UI loads the stored schema graph for that active database.
- If no schema graph exists, the Schema Graph window stays empty without warning.

### Duplicate database name rule

Implemented the agreed rule:

- `Test Connection` allows duplicate names and does not save the profile.
- `Save / Connect` rejects duplicate database display names with:

```text
DATABASE_NAME_ALREADY_EXISTS
```

### Multi-schema backend store

Added persistent backend schema graph storage:

```text
Data/SchemaGraph/index.json
Data/SchemaGraph/schemas/<database_profile_id>.schema_graph.json
```

New file:

```text
DataStore/schema_graph_store.py
```

Schema graphs are keyed internally by `database_profile_id`, while the UI displays the database name.

### Schema Graph APIs

Added backend APIs:

```text
GET    /schema-graph
GET    /schema-graph/active
POST   /schema-graph/active/refresh
DELETE /schema-graph/active
DELETE /schema-graph
```

Behavior:

- `GET /schema-graph/active` returns an empty schema state when no schema is stored.
- `POST /schema-graph/active/refresh` introspects the active database and saves the graph.
- `DELETE /schema-graph/active` deletes the active database schema graph.
- `DELETE /schema-graph` resets all stored schema graphs.

### Schema Graph UI window

Added a Schema Graph panel in the right sidebar:

- Shows active database schema status.
- Renders table nodes as cards.
- Renders relationships as join-condition edge rows.
- Has buttons:
  - Refresh
  - Delete
  - Reset

### Slash commands

Added slash commands:

```text
/Reset_schema
/Delete_schema
```

Behavior:

- `/Reset_schema` deletes all stored schema graphs.
- `/Delete_schema` deletes only the active database schema graph.

### Text-to-query schema context

Updated `Agent/agent_runtime.py`:

- Uses active database schema graph when available.
- Sends summarized schema graph context to the LLM.
- Does not auto-read DB schema on every query.
- If no stored schema exists, the LLM gets a conservative “no stored schema” context.

### `/Execute` workflow

Updated `/Execute` behavior:

- UI sends `/Execute` request to `/agent/chat`.
- Backend generates SQL using active model and active database context.
- Generated SQL is placed into Execute Box.
- User still reviews/edits SQL.
- User then runs `Check Safety`.
- User then clicks `Execute`.
- Write/DDL SQL can be drafted, but SQL Guard blocks execution in read-only mode.

### Real DB execution fix

Patched driver secret resolution:

```text
Gateway/db_drivers/base.py
```

Runtime materialized secrets from `.env` are now accepted by DB drivers, without persisting raw secrets into JSON profiles.

### Supabase REST support

Added:

```text
Gateway/db_drivers/supabase_rest_driver.py
```

Support includes:

- REST connection test through existing backend flow.
- OpenAPI-based schema introspection when Supabase REST exposes it.
- Simple read-only SELECT execution through PostgREST for queries like:

```sql
SELECT * FROM table LIMIT 10;
SELECT col1, col2 FROM table WHERE id = 1 LIMIT 10;
```

Unsupported arbitrary SQL returns a clear `SUPABASE_REST_SQL_UNSUPPORTED` error.

## Changed files

- `Apps/Web/index.html`
- `Apps/Web/styles.css`
- `Apps/Web/safy-ui.js`
- `Apps/Api/safy_api/main.py`
- `Agent/agent_runtime.py`
- `DataStore/schema_graph_store.py`
- `Gateway/db_drivers/base.py`
- `Gateway/db_drivers/factory.py`
- `Gateway/db_drivers/supabase_rest_driver.py`
- `Configs/app.yaml`
- `SOUL.md`

## Not changed

- `.env` was not included.
- Runtime data was not included.
- Existing database profile JSON was not included.
- Existing Data/SchemaGraph runtime cache was not included.

## Verification

Executed:

```bash
node --check Apps/Web/safy-ui.js
python -m py_compile Apps/Api/safy_api/main.py Apps/Api/safy_api/schemas.py Agent/agent_runtime.py DataStore/schema_graph_store.py Gateway/db_drivers/base.py Gateway/db_drivers/factory.py Gateway/db_drivers/supabase_rest_driver.py Gateway/query_orchestrator.py DataStore/profile_store.py DataStore/env_writer.py DataStore/env_secret_resolver.py DataStore/config_loader.py DataStore/user_store.py
```

Result: PASS.

## Manual smoke workflow

1. Start backend.
2. Login.
3. Open Database Management.
4. Test Connection with any name, including duplicate name.
5. Save / Connect with unique name.
6. Use Switch Database to choose active DB.
7. Schema Graph window should stay empty if no schema is stored.
8. Click Refresh in Schema Graph panel.
9. Type `/Execute show 5 rows from users`.
10. Generated SQL should appear in Execute Box.
11. Click Check Safety.
12. Click Execute if allowed.

## Final status

SAFY_SCHEMA_GRAPH_TEXT2QUERY_WORKFLOW_FIXED
