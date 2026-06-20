# SAFY Database Username Mapping Fix Report

## Problem

The SAFY login username was saved and displayed in the header, but the Database Management `USERNAME` input still showed the database profile value, for example:

```text
supabase_rest
```

Expected behavior:

```text
Database Management USERNAME = current SAFY backend user profile username
```

## Fix

### Frontend: `Apps/Web/safy-ui.js`

Updated username priority:

1. `safyUserProfile.username`
2. `safyRuntimeUsername`
3. legacy database profile username fallback only when no user profile exists

Changed functions:

- `applySafyRuntimeUser()`
- `syncDatabaseFields()`
- `databaseFormBody()`

The Database Management input now follows the logged-in backend username after login and when opening the Database panel.

### Backend: `Apps/Api/safy_api/main.py`

Updated `_prepare_database_payload_for_env()` so database profile saving always binds:

```text
profile.username = active SAFY backend user profile username
```

when an active user profile exists.

Base URL and database API key behavior remain unchanged:

- Base URL stays in database profile.
- API key/password/raw secret are written to `.env`.
- Database profile stores only env references.

## Expected behavior

If the current SAFY user is:

```text
Sadowiz
```

then Database Management should show:

```text
USERNAME = Sadowiz
```

not:

```text
supabase_rest
```

Saving or testing the database will send/use `Sadowiz` as the profile username.

## Verification

Executed:

```bash
node --check Apps/Web/safy-ui.js
python -m py_compile Apps/Api/safy_api/main.py Apps/Api/safy_api/schemas.py DataStore/profile_store.py DataStore/env_writer.py DataStore/env_secret_resolver.py DataStore/config_loader.py DataStore/user_store.py
```

Result: PASS.

## Final status

SAFY_DATABASE_USERNAME_MAP_FIXED
