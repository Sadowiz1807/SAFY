# SAFY

SAFY is a local AI Database Agent and Database Safety Gateway. It provides a local FastAPI backend, a static Web UI, database profile management, SQL safety checks, read-only query display, sandbox-first write/DDL validation, and workflow/audit boundaries between the user/agent and connected databases.

The canonical project status document is:

```text
Docs/SAFY_CURRENT_PROJECT_STATUS.md
```

Use that document as the source of truth for the current architecture, safety matrix, sandbox workflow, compatibility status, test matrix, and next phases.

---

## Current Runtime Status

SAFY currently supports:

- Local dashboard at `http://127.0.0.1:8000/`.
- Model profile management through OpenAI-compatible providers/local routers.
- Database profile management with secrets stored through local environment variables.
- Direct read-only query workflow for safe `SELECT`/show-data requests.
- Execute Box workflow for user-reviewed SQL.
- Sandbox-first validation for write/DDL SQL before real database execution.
- Deterministic SQL safety policy and workflow reviewer checks.
- Supabase execution through RPC when configured.
- Runtime/audit trace boundaries with row/secret redaction.
- Dark/light UI mode, client-side streaming/typewriter UI, and auto-run read-only setting.

SAFY is **not** an unrestricted production database administration tool. Destructive SQL such as `DROP` and `TRUNCATE` is blocked or requires a stronger administrative workflow.

---

## Safety Boundary

| Operation | Current behavior |
|---|---|
| `SELECT` / show data | Guarded read-only execution, no sandbox required |
| Broad/sensitive `SELECT` | May be limited, blocked, or require confirmation depending on policy |
| `CREATE`, `INSERT`, `UPDATE`, `DELETE`, `ALTER` | Draft/review first, then Check Safety in sandbox, then explicit Execute |
| `DROP`, `TRUNCATE`, permission/server/security statements | Blocked by default or require strong administrative confirmation |
| Secrets/API keys/passwords | Must stay in `.env` or local environment only; never commit raw secrets |

---

## Installation

From the repository root:

```powershell
python -m pip install -e .
```

Start SAFY and open the dashboard:

```powershell
safy run
```

Start SAFY without opening a browser:

```powershell
safy run --no-browser
```

The FastAPI app is defined in:

```text
Apps/Api/safy_api/main.py
```

The dashboard is served at:

```text
http://127.0.0.1:8000/
```

If Windows does not recognize `safy`, make sure Python's Scripts directory is on `PATH`, then retry:

```powershell
safy info
safy run --no-browser
```

---

## Optional Database Dependencies

Install optional database drivers when needed:

```powershell
python -m pip install -r requirements-db.txt
```

Some database targets require local client libraries or Docker services.

---

## Docker / Local Database Services

Current helper scripts use these names:

```powershell
Scripts\check_docker_runtime.ps1
Scripts\start_database_services.ps1
Scripts\stop_database_services.ps1
Scripts\start_docker_runtime.ps1
Scripts\stop_docker_runtime.ps1
```

Docker local configuration should be based on example files only. Do not commit real Docker `.env` files.

```text
Docker/.env.example
```

---

## Supabase RPC Setup

For Supabase write/DDL execution through base URL + API key mode, install the RPC function in your Supabase project:

```text
Scripts/supabase_safy_execute_sql_rpc.sql
```

Supabase base URL + API key mode is separate from native PostgreSQL password/host/port mode. SAFY still applies SQL Guard and sandbox-first validation before real write/DDL execution.

---

## Basic Usage

1. Start the backend with `safy run`.
2. Open `http://127.0.0.1:8000/`.
3. Create/select a model profile.
4. Create/select a database profile.
5. Test the database connection.
6. Refresh/load schema context.
7. Use chat or Execute Box.

Read-only example:

```text
hãy show ra các dữ liệu trong bảng datatest
```

Write/DDL example:

```sql
CREATE TABLE STUDENT (
  thne TEXT
);
```

Expected DDL workflow:

```text
SQL draft
→ Check Safety
→ sandbox validation
→ explicit Execute
→ real database execution
```

---

## Important API Endpoints

```text
GET  /health
POST /agent/chat
GET  /agent/skills
GET  /agent/tools
GET  /agent/state/{chat_id}
GET  /agent/workflow/{chat_id}
POST /query/check
POST /query/execute
GET  /database-profiles
POST /database-profiles
GET  /model-profiles
POST /model-profiles
GET  /schema-graph/active
POST /schema-graph/active/refresh
```

All real database execution must pass through the guarded query workflow.

---

## Static Validation

Run these checks after changes:

```powershell
python -m compileall -q Agent Core Tools State Apps/Api/safy_api Gateway Skills Audit DataStore LLM Providers Sandbox Toolsets
node --check Apps/Web/safy-ui.js
```

If/when a committed test suite exists, place it under a canonical `Tests/` folder and update this README with exact commands. The current package configuration does not require a `Tests` package.

---

## Push-clean / Git Safety

Before pushing:

```powershell
gitleaks detect --source . --verbose
```

Runtime/local-only files must not be committed:

```text
.env
.env.*
Data/secrets/
Data/sessions/
Data/sandboxes/
Sandbox/workspaces/
Data/**/*.db
Data/**/*.sqlite
Data/**/*.sqlite3
*.local.json
Docker/.env
*.log
```

If a file was already tracked by Git, `.gitignore` alone is not enough. Remove it from the index:

```powershell
git rm --cached --ignore-unmatch .env
git rm --cached -r --ignore-unmatch Data/secrets
git rm --cached -r --ignore-unmatch Data/sessions
git rm --cached -r --ignore-unmatch Data/sandboxes
git rm --cached -r --ignore-unmatch Sandbox/workspaces
```

---

## Project Structure

```text
Agent/        Agent runtime and schema context
Apps/Api/     FastAPI backend
Apps/Web/     Static dashboard UI
Audit/        Audit schema/store/logger
Configs/      Runtime configuration
Core/         Workflow state, policy, reviewer, registries
DataStore/    Profile/env/schema stores
Gateway/      SQL guard, query orchestrator, DB adapters
LLM/          Model profile/provider adapters
Providers/    Provider registry and mock/demo providers
Sandbox/      Sandbox manager, Docker manager, workspace lifecycle
Scripts/      Local helper scripts and setup utilities
Skills/       Skill packages and runtimes
State/        Runtime/session/workflow state
Tools/        Tool registry, schemas, SQL/database/sandbox tools
Toolsets/     Runtime toolset helpers
Docs/         Canonical docs, reports, and architecture notes
```

---

## Troubleshooting

### `package directory 'Tests' does not exist`

This was caused by `pyproject.toml` listing a `Tests` package while the repository did not contain a `Tests/` directory. The package list should not include `Tests` unless that folder exists and is committed.

### `SANDBOX_SECRET_MISSING`

The real database key may exist in `.env`, but sandbox internal credential references may be stale or missing. Reconnect/save the database profile, ensure sandbox, or clear stale local runtime sandbox state and let SAFY recreate it.

### SELECT still asks for Execute

Check the auto-run read-only UI setting and verify the backend classifies the request as `READ_ONLY_SQL`.

### Write/DDL does not auto-run

This is expected. Write/DDL must pass sandbox validation and explicit user execution.

---

## Roadmap

Next major work should focus on:

1. Canonical regression tests.
2. Text_to_query v2 with examples/tests/templates.
3. Tool trace/debug UI.
4. True backend streaming through SSE/WebSocket.
5. Broader live validation for optional database drivers.
