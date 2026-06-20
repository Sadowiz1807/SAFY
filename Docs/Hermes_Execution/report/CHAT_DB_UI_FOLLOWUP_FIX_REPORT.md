# SAFY Chat/Database UI Follow-up Fix Report

## Scope

Fixed only the new issues reported after the previous database/sandbox and chat command pass.

No database Save/Test raw-secret workflow was refactored.
No model profile save/test flow was changed.
No `/Execute` safety bypass was introduced.

## Issues fixed

### 1. `/Execute` could fail with AGENT_RUNTIME_ERROR when the LLM returned non-JSON text

`AgentRuntime.generate_sql()` previously expected structured JSON from the LLM. Small local models can return normal text instead. That produced an agent runtime error such as `LLM did not return structured JSON/string`, which the UI then mapped incorrectly as model unreachable.

Fix:

- Added robust LLM content normalization.
- Non-string/dict/list content is converted safely.
- If no JSON is returned, SAFY no longer throws a runtime error.
- If no SQL is found, SAFY returns a safe assistant answer with no execution.

### 2. `/Execute tạo database/bảng...` should not call the LLM as a normal SQL generation path

The user tested write/DDL-style commands such as creating a database/table. SAFY is currently read-only guarded. These commands should be blocked clearly, not fail with model/server messages.

Fix:

- Added write/DDL detection in `Agent/agent_runtime.py`.
- `/Execute create table`, `/Execute tạo database`, `/Execute tạo bảng`, insert/update/delete/drop/alter/truncate are blocked locally by read-only guard.
- No SQL execution is attempted.
- Response is returned as a normal successful SAFY safety answer, not backend error.

### 3. Agent response formatting did not show `answer` clearly

The UI formatter did not prioritize `reply.answer`, so backend guard answers could be hidden behind generic execution-mode text.

Fix:

- `formatAgentReply()` now shows `answer` first.
- If the response is a simple answer with no generated SQL/check/execute, the chat bubble displays the answer directly.

### 4. Slash command menu was visually unreadable

The menu was too dark/low contrast and did not look selectable.

Fix:

- Slash command menu is now white.
- Command rows are clickable/selectable.
- Active/hover item uses blue highlight.
- Menu height is capped to show up to 5 rows; extra commands scroll.
- Selected item scrolls into view on arrow navigation.

### 5. Selected slash command needed visible state

Native textarea/input cannot partially color only `/Execute`, so SAFY now uses a visible command chip and input highlight.

Fix:

- Selecting `/Execute` inserts it into the input.
- A white/blue command chip appears above the input.
- Chat input gets a blue left accent and border while a valid command is active.

### 6. Database Management fields were not synced from canonical stored profile

When reopening the UI, the Database card could show connected, while the management form still showed stale/default/mock values.

Fix:

- `loadProfiles()` now ignores empty active payloads without profile IDs.
- The database config form syncs from `/database-profiles/active`.
- `Connection Name`, `Base URL`, and `Username` are populated from the active canonical profile.
- API key remains redacted in the UI, with placeholder: `Saved in backend; leave blank to keep existing key`.

### 7. Preserve saved backend secret when UI field is blank

Because public API responses do not echo raw secrets back to the browser, reopening the form leaves the API key field empty. Clicking Save should not erase the existing key.

Fix:

- Frontend sends `preserve_secret: true` when API key is blank but backend reports `has_raw_secret`.
- Backend merges the already-saved raw secret before test-before-save.
- The raw secret is still not returned to UI responses.

## Files modified

- `Apps/Web/mock-ui.js`
- `Apps/Web/styles.css`
- `Apps/Api/safy_api/main.py`
- `Agent/agent_runtime.py`

## Verification

Executed successfully:

```bash
node --check Apps/Web/mock-ui.js
python -m py_compile Apps/Api/safy_api/main.py Agent/agent_runtime.py
```

Result: PASS.

## Expected behavior

1. Open UI after backend already has active database profile:
   - Database card shows real connected.
   - Database Management fields show the saved Connection Name/Base URL/Username.
   - API key is not echoed, but placeholder shows it is saved in backend.

2. Type `/`:
   - White command menu appears.
   - Up to 5 commands are visible.
   - Extra commands scroll.
   - Hover/arrow selected command is highlighted blue.

3. Select `/Execute`:
   - `/Execute` is inserted into input.
   - Command chip appears above input.
   - Input border/left accent changes blue.

4. Send `/Execute tạo 1 database có cột name và id`:
   - SAFY returns a read-only guard block message.
   - No AGENT_RUNTIME_ERROR.
   - No fake model server unreachable error.

5. Normal non-database chat:
   - Can still call LM Studio.

## Remaining note

If the product later needs real write/DDL actions such as creating tables or databases, that must be a separate privileged workflow with explicit permission mode and confirmation. This pass keeps the current read-only safety boundary.
