# SAFY

SAFY is a local-first AI Database Agent and Database Safety Gateway. It provides a web dashboard for connecting to databases, asking database questions, generating SQL, validating SQL through a sandbox, and executing approved operations through a guarded workflow.

SAFY is designed for local development and controlled database operations. It is not an unrestricted production DBA tool.

---

## Highlights

- Local dashboard at `http://127.0.0.1:8000/`
- Chat-based database assistant
- Read-only data display directly in chat
- Execute Box for reviewing generated SQL
- SQL safety classification before execution
- Sandbox-first validation for write and DDL statements
- Supabase RPC execution path
- PostgreSQL/MySQL/SQLite-oriented driver layer
- Model profile management through OpenAI-compatible endpoints
- Database profile management with local environment secrets
- Workflow state, audit boundary, and redaction rules
- Dark/light UI mode
- Client-side streaming/typewriter UI
- Auto-run read-only setting

---

## Safety Model

SAFY separates database operations by risk class.

| Operation type | Example | Behavior |
|---|---|---|
| Read-only | `SELECT * FROM users LIMIT 100` | Runs through read-only guard and returns results in chat |
| Write | `INSERT`, `UPDATE`, `DELETE` | Requires sandbox check before real execution |
| DDL | `CREATE TABLE`, `ALTER TABLE` | Requires sandbox check before real execution |
| Destructive | `DROP`, `TRUNCATE`, broad delete/update | Blocked by default or requires stronger confirmation |
| Secret access | API keys, passwords, tokens | Blocked/redacted |

Core rule:

```text
Read-only query → direct guarded read
Write/DDL query → sandbox validation → explicit Execute → real database
Destructive query → block or strong confirmation workflow
```

---

## Quick Start

From the repository root:

```powershell
python -m pip install -e .
```

Start SAFY:

```powershell
safy run
```

Start without opening the browser:

```powershell
safy run --no-browser
```

Open the dashboard:

```text
http://127.0.0.1:8000/
```

Check CLI metadata:

```powershell
safy info
```

---

## Requirements

Minimum runtime:

- Python 3.10+
- Windows PowerShell or CMD
- Browser for the local dashboard

Optional runtime:

- Docker Desktop for Docker-backed sandbox/database services
- Database driver dependencies from `requirements-db.txt`
- Supabase project with RPC setup for Supabase write/DDL execution

Install optional database dependencies:

```powershell
python -m pip install -r requirements-db.txt
```

---

## First Setup

### 1. Start the app

```powershell
safy run --no-browser
```

Then open:

```text
http://127.0.0.1:8000/
```

### 2. Configure a model profile

Use the UI to configure an OpenAI-compatible model endpoint.

Typical profile fields:

```text
base_url
model
api_key_env
```

Raw API keys must stay in `.env` or OS environment variables. Do not commit real keys.

### 3. Configure a database profile

Use the UI to configure a database connection.

Typical profile fields:

```text
provider
driver
host/base_url
database
username
password_env/api_key_env
```

Test and activate the profile before using the chat or Execute Box.

### 4. Use the assistant

Read-only example:

```text
hãy show ra các dữ liệu trong bảng datatest
```

DDL example:

```sql
CREATE TABLE STUDENT (
  thne TEXT
);
```

Expected DDL flow:

```text
SQL draft
→ Check Safety
→ sandbox validation
→ Execute
→ real database execution
```

---

## Supabase RPC Setup

For Supabase base URL + API key mode, SAFY uses an RPC execution path for write/DDL operations.

Install the RPC function from:

```text
Scripts/supabase_safy_execute_sql_rpc.sql
```

Supabase RPC mode is separate from native PostgreSQL mode.

```text
Supabase mode:
base URL + API key + RPC

Native PostgreSQL mode:
host + port + database + username + password
```

Write/DDL operations still require SAFY safety checks before real execution.

---

## Docker and Local Database Services

Current helper scripts:

```powershell
Scripts\check_docker_runtime.ps1
Scripts\start_database_services.ps1
Scripts\stop_database_services.ps1
Scripts\start_docker_runtime.ps1
Scripts\stop_docker_runtime.ps1
```

Example Docker env file:

```text
Docker/.env.example
```

Do not commit real Docker `.env` files.

---

## Main API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Backend health check |
| `POST` | `/agent/chat` | Main chat workflow |
| `GET` | `/agent/skills` | List registered skills |
| `GET` | `/agent/tools` | List registered tools |
| `GET` | `/agent/state/{chat_id}` | Inspect session state |
| `GET` | `/agent/workflow/{chat_id}` | Inspect workflow trace |
| `POST` | `/query/check` | Check SQL safety |
| `POST` | `/query/execute` | Execute approved SQL |
| `GET` | `/database-profiles` | List database profiles |
| `POST` | `/database-profiles` | Save database profile |
| `GET` | `/model-profiles` | List model profiles |
| `POST` | `/model-profiles` | Save model profile |
| `GET` | `/schema-graph/active` | Read active schema graph |
| `POST` | `/schema-graph/active/refresh` | Refresh active schema graph |

---

## Project Structure

```text
Agent/        Agent runtime and schema context
Apps/Api/     FastAPI backend
Apps/Web/     Static dashboard UI
Audit/        Audit schema, store, logger
Configs/      Runtime configuration
Contracts/    API/contracts/spec references
Core/         Workflow state, policy, reviewer, registries
Data/         Example/runtime data boundary
DataStore/    Profile/env/schema stores
Docker/       Docker compose files and examples
Docs/         Canonical documentation
Gateway/      SQL guard, query orchestrator, database adapters
LLM/          Model profile/provider adapters
Logging/      Logging helpers
Providers/    Provider registry and demo/mock providers
Sandbox/      Sandbox manager, Docker manager, workspace lifecycle
Scripts/      Local helper scripts and setup utilities
Skills/       Skill packages and runtimes
State/        Runtime/session/workflow state
Tools/        Tool registry, schemas, SQL/database/sandbox tools
Toolsets/     Runtime toolset helpers
```

Canonical project status document:

```text
Docs/SAFY_CURRENT_PROJECT_STATUS.md
```

---

## Development Checks

Run static validation:

```powershell
python -m compileall -q Agent Core Tools State Apps/Api/safy_api Gateway Skills Audit DataStore LLM Providers Sandbox Toolsets
node --check Apps/Web/safy-ui.js
```

Run install check:

```powershell
python -m pip install -e . --dry-run
python -m pip install -e .
```

Run the server:

```powershell
safy run --no-browser
```

---

## Git Safety

Before pushing:

```powershell
gitleaks detect --source . --verbose
```

Never commit:

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

## Troubleshooting

### `package directory 'Tests' does not exist`

The package list should not include `Tests` unless the repository contains a committed `Tests/` package.

Check:

```powershell
python -m pip install -e . --dry-run
```

### `safy` is not recognized

Ensure Python Scripts is on `PATH`, then reopen the terminal.

Typical user-level paths on Windows include:

```text
%APPDATA%\Python\Python312\Scripts
%LOCALAPPDATA%\Microsoft\WindowsApps
```

### `SANDBOX_SECRET_MISSING`

The real database key may exist in `.env`, but sandbox internal credential references may be stale.

Recommended recovery:

```text
1. Restart SAFY.
2. Reconnect or save the database profile.
3. Ensure sandbox again.
4. If needed, clear stale local Data/sandboxes and Data/secrets, then recreate sandbox.
```

### SELECT still asks for Execute

Check:

```text
- Auto-run read-only setting is enabled.
- The generated SQL is classified as READ_ONLY_SQL.
- Browser cache is refreshed with Ctrl+F5.
```

### Write/DDL does not auto-run

This is expected. Write/DDL must pass sandbox validation and explicit user execution.

---

## Documentation

Main documents:

```text
Docs/SAFY_CURRENT_PROJECT_STATUS.md
Docs/DOCUMENTATION_INDEX.md
```

Patch reports and older architecture notes may exist under `Docs/` and `Docs/Hermes_Execution/`. The current status document is the primary reference for architecture and safety policy.

---

## Roadmap

Next major work:

1. Canonical regression tests.
2. `Text_to_query` v2 with examples, tests, templates, and deterministic Vietnamese intent handling.
3. Tool trace/debug UI.
4. True backend streaming through SSE or WebSocket.
5. Broader live validation for optional database drivers.
6. Documentation cleanup and stable release checklist.
