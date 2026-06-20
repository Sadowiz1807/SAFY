# SAFY Login Logic Fix Report

## Problem

The login screen could show a database-related error while the user was logging in. Login must be independent from database connection state.

Observed UI error:

```text
Database connection failed. Check Base URL, API Key, username, and backend secret handling.
```

This was wrong for the login flow.

## Fix

### Frontend

Updated `Apps/Web/safy-ui.js`:

- Auth errors are handled before database/secret error mapping.
- Login catch block no longer double-normalizes errors.
- Non-auth backend failures during login now show a login-specific message instead of a database connection message.

### Backend

Updated `Apps/Api/safy_api/main.py`:

- Added `_resolve_or_repair_login_password()`.
- If `.env` is missing or the login password env entry is empty/broken, backend repairs it with the local default password.
- Correct password `123456` can enter the dashboard even if database connection/profile secret state is broken.
- Login no longer depends on database secret handling.

## Expected behavior

- Correct username + password `123456` enters the dashboard.
- Wrong password shows:

```text
Invalid password.
```

- Database connection errors should not appear on the login screen.
- Database connection errors should only appear when testing/saving/using the database connection.

## Verification

Executed:

```bash
node --check Apps/Web/safy-ui.js
python -m py_compile Apps/Api/safy_api/main.py Apps/Api/safy_api/schemas.py DataStore/profile_store.py DataStore/env_writer.py DataStore/env_secret_resolver.py DataStore/config_loader.py DataStore/user_store.py
```

Result: PASS.

## Final status

SAFY_LOGIN_LOGIC_FIXED
