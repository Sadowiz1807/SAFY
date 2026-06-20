# SAFY Database Secret Storage Hotfix Report

## Problem

Save Database still returned:

```text
SECRET_VALUE_REJECTED
Raw secret values must not be stored in profiles.
```

The submitted payload contained transient raw database secret fields such as `api_key` and `raw_secret`.

## Root cause

Some code paths could still let the raw database secret reach profile validation before it was moved to `.env`, or the stricter profile store could reject the secret before the route completed env migration.

## Fix

### Backend API

Updated:

```text
Apps/Api/safy_api/main.py
```

Changes:

- Save Database uses a secret-free payload for duplicate endpoint checking.
- Save Database moves raw DB secret to `.env` before profile normalization.
- `_save_database_profile_payload()` now has a last-line defense: every database save goes through `_prepare_database_payload_for_env()` before reaching the JSON profile store.

### Profile store

Updated:

```text
DataStore/profile_store.py
```

Changes:

- Database profiles are now env-only at storage time.
- If raw DB secret reaches the store directly, it returns `SECRET_ENV_REQUIRED` instead of allowing raw persistence.
- Raw DB secret fields are never written to JSON profile storage.

### Provider/OpenRouter support

Included the previous provider secret fix to ensure OpenRouter raw API keys are stored into `.env` and profile JSON stores only `api_key_env`.

## Files changed

- `Apps/Api/safy_api/main.py`
- `DataStore/profile_store.py`
- `Apps/Web/safy-ui.js`
- `LLM/provider_adapters/openai_compatible.py`
- `LLM/provider_profiles.py`

## Validation

Passed:

```bash
python -m py_compile <all project .py files>
node --check Apps/Web/safy-ui.js
functional smoke: user-shaped Supabase payload with api_key/raw_secret -> .env ref -> profile save without raw secret
```

## Final status

SAFY_DATABASE_SECRET_STORAGE_HOTFIXED
