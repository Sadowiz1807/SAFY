# Phase 1 UI Spec - Contract-first Foundation

Source of truth: `C:/Users/ASUS/SAFY/Docs_prior_project/SAFY_source.md`

Status: historical Phase 1 planning contract. Phase 1 gate reports record completed mock/skeleton work; this artifact remains the contract reference and does not authorize real LLM, sandbox, or database execution.

## Layout
Header:
- Safy logo/name.
- Model status.
- Database status.
- Sandbox status.

Left sidebar:
- New session button.
- Session history.
- Model connection button/icon.
- Database connection button/icon.
- Settings button.

Main chat area:
- Chat messages.
- Prompt input.
- Agent response.
- Technical output area.

Right execution sidebar:
- Agent result panel.
- Workflow status.
- Generated SQL / validated SQL panels.
- Schema summary.
- User query box.
- Check button.
- Safety Report panel.
- Yes/No execute controls.
- Visible high-risk backend `confirmation_code` display.
- 4-digit confirmation code input.
- Execution result/error panel.

## Model Connection Modal
Fields: `profile_name`, `provider`, `base_url`, `model`, `api_key`, `temperature`, `max_tokens`, save button, test connection button.

Rules:
- API response must never display raw `api_key`.
- UI can display masked status such as `secret_configured: true`.
- Existing profile overwrite must require explicit confirmation.

## Database Connection Modal
Fields: `profile_name`, `dbms`, `host`, `port`, `database`, `username`, `password`, `ssl`, `user_query_access_mode`, save button, test connection button.

Rules:
- API response must never display raw `password`.
- UI can display masked status such as `secret_configured: true`.
- Existing profile overwrite must require explicit confirmation.

## Right Sidebar Query Flow
1. User enters SQL/query.
2. User clicks Check.
3. UI calls `/query/check`.
4. UI displays Safety Report.
5. Low/medium risk: show Yes/No controls.
6. High-risk: display backend-generated visible 4-digit `confirmation_code` and show input for user to type it.
7. Execute button stays disabled until user chooses Yes and enters code when required.
8. UI calls `/query/execute` only after user decision.
9. UI displays success result or normalized error.

## Mock States Required
- New session active.
- Model connected/disconnected.
- Database connected/disconnected.
- Sandbox healthy/unavailable.
- Agent response with generated SQL and schema summary.
- Low-risk SELECT check.
- High-risk DELETE/DROP/UPDATE/ALTER check with visible code.
- Execute success.
- Execute errors: missing check, invalid code, expired code, DB permission denied.


Legacy field note: `access_mode` is a Phase 1 legacy alias; current canonical field is `user_query_access_mode`.
