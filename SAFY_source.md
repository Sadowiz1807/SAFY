# SAFY Source Map

Canonical runtime source files:

- `Apps/Api/safy_api/main.py`: API routes, profile lifecycle, user Execute Box workflow.
- `Apps/Web/index.html`: application shell.
- `Apps/Web/safy-ui.js`: browser runtime orchestration.
- `Gateway/query_orchestrator.py`: SQL safety, sandbox validation, real execution gate.
- `Gateway/real_db_policy.py`: agent-direct real database read-only policy.
- `Gateway/db_drivers/`: real database drivers.
- `Sandbox/sandbox_manager.py`: Docker/local sandbox lifecycle and validation.
- `DataStore/`: profile, env, and schema graph storage.
- `Skills/`: composable runtime skills.

Runtime data is stored under `Data/` and is intentionally resettable.
