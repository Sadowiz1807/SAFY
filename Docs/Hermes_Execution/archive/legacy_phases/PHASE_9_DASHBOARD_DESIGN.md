# Phase 9 Dashboard Design

## Required Routes

- `GET /` -> dashboard HTML or redirect to dashboard.
- `GET /docs` -> FastAPI developer Swagger/OpenAPI docs only.
- `GET /openapi.json` -> OpenAPI schema.
- `GET /health` -> JSON health/status.

## Preferred Serving Plan

`GET /` should return `Apps/Web/index.html`. Static assets should be served under `/static/...` or `/web/...` from `Apps/Web`. Current files inspected/planned: `Apps/Web/index.html`, `Apps/Web/mock-ui.js`, and `Apps/Web/styles.css`.

## Health Response

```json
{
  "success": true,
  "data": {
    "name": "SAFY",
    "version": "1.1.0",
    "status": "ok",
    "mode": "real_connected_db_readonly"
  },
  "error": null
}
```

## Why `/docs` Remains Available

`/docs` is required for developer/API validation and should not be repurposed as the user dashboard. The user-facing entrypoint is `/`.

## Launcher Integration

`safy run` starts the backend, waits for readiness, and opens `http://127.0.0.1:8000/`. `--no-browser` starts the server without browser launch.

## Validation

- Fetch `/` and verify HTML loads.
- Fetch `/static` or `/web` assets and verify JS/CSS load.
- Fetch `/docs` and verify Swagger still loads.
- Fetch `/openapi.json` and verify schema still loads.
- Fetch `/health` and verify standard SAFY envelope.

## Safety Notes

Dashboard serving must not bypass API safety boundaries. User SQL and agent SQL still go through `/query/check` and `/query/execute`. Static rendering must not expose raw driver errors, credentials, tracebacks, or untrusted HTML.
