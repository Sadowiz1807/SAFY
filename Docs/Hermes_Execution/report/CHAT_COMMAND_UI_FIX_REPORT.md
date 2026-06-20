# SAFY Chat Command + Chat UI Fix Report

## Scope

Fixed only the newly identified chat issues:

1. Database-operation prompts without `/Execute` were still reaching LM Studio.
2. `/Execute` did not always send the active database profile explicitly.
3. Chat bubble layout needed user messages on the right, Safy messages on the left.
4. Short messages should not stretch across the full chat width.
5. Typing `/` in the chat input should show a command menu.

No database Save/Test workflow was changed in this pass.
No model profile flow was changed in this pass.
No raw-secret/database-profile storage logic was changed in this pass.

---

## Files modified

- `Apps/Web/mock-ui.js`
- `Apps/Web/styles.css`
- `Apps/Api/safy_api/main.py`
- `Agent/agent_runtime.py`

---

## Frontend changes

### `Apps/Web/mock-ui.js`

Added SAFY slash command menu support:

- `/Execute`
- `/Inspect`
- `/Help`
- `/Cancel`
- `/Reset`

Behavior:

- Typing `/` opens the command menu.
- Typing more characters filters the command menu.
- `ArrowUp` / `ArrowDown` changes selected command.
- `Enter` / `Tab` inserts the selected command.
- `Escape` closes the menu.
- Clicking a command inserts it into the chat input.

Added database-operation guard:

- If the user enters a database operation such as `tạo bảng`, `create table`, `select ... from`, `insert`, `update`, `delete`, etc. without `/Execute`, SAFY renders a local assistant guard message and does not call `/agent/chat`.
- This prevents those database operation prompts from being logged in LM Studio as normal chat.

Updated `/Execute` payload:

```json
{
  "chat_id": "<session_id>",
  "message": "<message without /Execute>",
  "model_profile_id": "<active model profile>",
  "database_profile_id": "<active database profile>",
  "target": "connected_database",
  "auto_execute": true,
  "options": {
    "command": "execute"
  }
}
```

Normal chat payload now includes:

```json
{
  "options": {
    "command": "chat"
  }
}
```

Local commands:

- `/Help` returns a local help message.
- `/Reset` clears the current chat draft.
- Unknown slash commands return a local warning.

---

## Backend changes

### `Apps/Api/safy_api/main.py`

Added `command_mode` from `payload.options.command`.

Changed auto target resolution:

- `target="auto"` is resolved to active database only when `command_mode == "execute"`.
- Normal chat no longer silently routes through connected database/sandbox.

Passes `command_mode` into `AgentRuntime.chat()`.

### `Agent/agent_runtime.py`

Added a database command gate:

- Database operation messages require `command_mode == "execute"`.
- If a database operation arrives without `/Execute`, backend returns a local guard message instead of calling LM Studio.

This gives a backend-level safety layer in case frontend guard misses a command.

---

## UI layout changes

### `Apps/Web/styles.css`

Updated chat message layout:

- User messages align right.
- Safy/assistant messages align left.
- Bubbles use `width: fit-content`.
- Bubbles have max width and wrap long text.
- Short messages no longer stretch across the whole screen.

Added slash command menu styling:

- Floating menu above chat input.
- Active/hover command state.
- Command name, title, and description.

---

## Verification

Executed successfully:

```bash
node --check mock-ui.js
python -m py_compile main.py agent_runtime.py
```

Result: PASS.

---

## Expected behavior after applying

### Case 1: User types `/`

Command menu appears.

### Case 2: User types `tạo bảng users` without `/Execute`

SAFY does not call LM Studio.
SAFY shows local message:

```text
Database đã kết nối. Để thao tác database, hãy bắt đầu tin nhắn bằng /Execute...
```

### Case 3: User types `/Execute tạo bảng users`

SAFY sends active model profile + active database profile to `/agent/chat`.
Database workflow is allowed to continue through guard/runtime.

### Case 4: Short chat message

Bubble remains compact instead of spanning the full screen.

---

## Remaining note

Normal non-database chat can still call LM Studio if the message is not classified as a database operation. This pass specifically blocks database-operation prompts without `/Execute`, which was the cause of the incorrect “please connect database” style responses.
