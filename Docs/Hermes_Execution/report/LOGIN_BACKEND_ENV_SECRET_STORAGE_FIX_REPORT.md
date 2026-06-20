# SAFY Login Backend + Env Secret Storage Fix Report

## Scope

This pass implements the requested login/user-profile/backend-env behavior and moves database API key persistence from JSON profiles to `.env`.

Modified files:

- `Apps/Web/index.html`
- `Apps/Web/styles.css`
- `Apps/Web/safy-ui.js`
- `Apps/Api/safy_api/main.py`
- `Apps/Api/safy_api/schemas.py`
- `DataStore/profile_store.py`
- `.env.example`

Copied unchanged support files into the package for convenience:

- `DataStore/env_writer.py`
- `DataStore/env_secret_resolver.py`
- `DataStore/config_loader.py`
- `DataStore/user_store.py`
- `Configs/app.yaml`

## Implemented behavior

### Login gate

- Dashboard no longer opens automatically from saved browser info.
- On every page load, SAFY shows the login screen first.
- Saved username is prefilled.
- If backend has a configured password env reference, password field shows `********`.
- User still must press `Login` to open the dashboard.
- Login button was enlarged and styled light blue with white text.

### Backend user profile

- Added `GET /auth/profile`.
- Added `GET /user/profile` alias.
- Added `POST /auth/login`.
- Username is stored in backend user profile at `Data/User/user_profiles.json`.
- User profile stores only symbolic password env reference: `SAFY_LOGIN_PASSWORD`.
- Real login password is resolved from `.env` / OS env.
- If `.env` does not exist or `SAFY_LOGIN_PASSWORD` is missing, backend creates `.env` with default local password `123456` on first local auth call. Empty `SAFY_LOGIN_PASSWORD=` entries are overwritten with the local default. Empty `SAFY_LOGIN_PASSWORD=` entries are overwritten with the local default.

### Database Management username mapping

- Database Management `Username` maps from backend user profile username.
- Database save/test falls back to backend username when the DB username field is empty.

### Database API key storage

- Base URL remains in database profile JSON.
- Database API key/password/raw_secret is treated as transient request data only.
- Backend writes database secret into `.env` using env name like:

```text
SAFY_DB_MAIN_DATABASE_API_KEY
```

- Database profile stores only references:

```json
{
  "secret_mode": "env",
  "password_mode": "env",
  "secret_env": "SAFY_DB_MAIN_DATABASE_API_KEY",
  "api_key_env": "SAFY_DB_MAIN_DATABASE_API_KEY",
  "password_env": "SAFY_DB_MAIN_DATABASE_API_KEY"
}
```

- Runtime driver calls materialize the secret from `.env` only at connection/test time.
- API responses do not echo raw secrets.

## Important local file behavior

The backend may create this local file at runtime:

```text
.env
```

Do not commit `.env`.

Keep this in `.gitignore`:

```text
.env
.env.*
!.env.example
Data/secrets/
Data/sessions/
Data/safy_profiles.json
Data/Database_management/database_profiles.json
Data/**/*.local.json
```

## Verification

Passed:

```bash
node --check safy-ui.js
python -m py_compile main.py schemas.py profile_store.py env_writer.py env_secret_resolver.py config_loader.py user_store.py
```

## Final status

SAFY_LOGIN_BACKEND_ENV_SECRET_STORAGE_FIXED
