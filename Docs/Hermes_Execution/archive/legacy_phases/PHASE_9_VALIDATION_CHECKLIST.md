# Phase 9 Validation Checklist

This checklist is for a future approved implementation pass. It is not executed as part of planning unless explicitly stated in a report.

## Compile / Static

```powershell
python -m compileall .
node --check Apps/Web/mock-ui.js
```

## Full Test Suite

```powershell
python -m pytest Tests/phase1 Tests/phase1_5 Tests/phase2 Tests/phase2_5 Tests/phase3 Tests/phase4 Tests/phase4_5 Tests/phase5 Tests/phase6 Tests/phase7 Tests/phase8 Tests/phase9 -q --basetemp=tmp/pytest_phase9_final
```

## Launcher Validation

```powershell
cd C:\Users\ASUS\SAFY
pip install -e .
cd C:\Users\ASUS
safy info
safy run --host 127.0.0.1 --port 8000
```

## No-browser Validation

```powershell
cd C:\Users\ASUS
safy run --host 127.0.0.1 --port 8000 --no-browser
```

Expected: `safy run` starts the gateway and opens the dashboard automatically. `safy run --no-browser` starts the gateway but does not open the browser.

## Endpoint Validation

- `GET http://127.0.0.1:8000/` -> dashboard HTML or redirect to dashboard.
- `GET http://127.0.0.1:8000/docs` -> developer API docs still load.
- `GET http://127.0.0.1:8000/openapi.json` -> OpenAPI schema still loads.
- `GET http://127.0.0.1:8000/health` -> JSON health/status if implemented.

## Secret Scan

```powershell
rg -n --hidden -S "sk-|Bearer |password=|api_key=|token=|postgres://|mysql://|Traceback|Exception|DSN|dsn" .
```

Classify matches as fixtures, docs, regexes, placeholders, or real leaks. Real raw secrets block release.

## Generated Artifact Scan

```powershell
git status --short
git ls-files | findstr /i "__pycache__ .pyc .pytest_cache tmp"
```

## Phase 9 Safety Validation

- No database drivers created.
- No write support enabled.
- `INSERT` remains blocked.
- SQL Guard is mandatory.
- `/query/check` does not execute SQL.
- `/query/execute` remains state-bound.
- Result rows are not persisted.
- Raw secrets are not persisted.
