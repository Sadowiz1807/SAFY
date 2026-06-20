# Hermes Validation Gates

## Purpose
Define gates Hermes must run before accepting stage/task output.

## Gate 0: Task Board Schema Gate
Hermes must run this gate before dispatching any sub-agent task.

Required fields for every dispatchable task in `04_TASK_BOARD.yaml`:
- `task_id`
- `title`
- `stage`
- `assigned_agent`
- `priority`
- `status`
- `dispatchable`
- `input_docs`
- `allowed_paths`
- `must_not_modify`
- `requirements`
- `acceptance_criteria`
- `validation_gate`
- `handoff_artifact`
- `definition_of_done`

Dispatch rules:
- No sub-agent may start a task unless `dispatchable: false`.
- Hermes cannot dispatch a task if any required schema field is missing or empty.
- API contract tasks must be fully expanded before API contract starts.
- Later stages may remain placeholders only when `dispatchable: false` and `status: planned_placeholder`.
- Hermes must expand placeholder tasks before starting their stage.
- `allowed_paths` and `must_not_modify` must be checked before accepting file changes.

## Gate 1: Source-of-truth
- Follows `SAFY_source.md`.
- Does not reintroduce old assumptions.
- Preserves new explicit user decisions from Hermes plan unless they conflict with source security.

## Gate 2: Security
Reject if output contains:
- Agent write/DDL on connected database.
- Raw API key/password in JSON.
- Raw secret in API response/log/audit/runtime DB.
- confirmation code produced by LLM.
- High-risk user query execution without 4-digit numeric confirmation.
- Query execution without safety check.
- User query execution treated as agent execution.

## Gate 3: UI
Must include:
- Chat-first layout.
- Left sidebar with sessions/settings/model/db connection.
- Right sidebar with agent result and user query box.
- Safety Report before execution.
- Yes/No decision controls.
- 4-digit code input for high-risk.

## Gate 4: Profile
Must include:
- Model API key saved to `.env`.
- Model JSON stores `api_key_env` only.
- DB password saved to `.env`.
- DB JSON stores `password_env` only.
- Overwrite requires confirmation.
- Responses mask secrets.

## Gate 5: Query Execution
Must include:
- `/query/check` never executes SQL.
- `/query/execute` requires prior valid check.
- High-risk requires valid 4-digit code.
- Wrong/expired code blocks.
- SQL/target change invalidates code.
- DB permission errors are normalized and displayed.

## Gate 6: Agent Behavior
Must include:
- Default e-commerce when domain missing.
- Assumption stated to user.
- Follow-up only when critical info missing.
- No quick-or-guided mode UI.
- Connected DB agent path remains read-only.
