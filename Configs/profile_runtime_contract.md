# Profile Runtime Contract - API contract

## user_profiles.json Schema
Model profile JSON stores only:
- `profile_id`
- `display_name`
- `provider`
- `base_url`
- `model`
- `api_key_env`
- `temperature`
- `max_tokens`

Raw API key is forbidden in JSON. Raw API key goes only to `.env`.

## database_profiles.json Schema
Database profile JSON stores only:
- `profile_id`
- `display_name`
- `dbms`
- `host`
- `port`
- `database`
- `username`
- `password_env`
- `ssl`
- `access_mode`

Raw DB password is forbidden in JSON. Raw DB password goes only to `.env`.

## .env Writer Contract
- Accept raw secret only from save request body.
- Derive deterministic env var name from profile id.
- Detect existing profile id and existing env var before writing.
- If either exists and `overwrite_confirmed` is false, return `PROFILE_OVERWRITE_CONFIRMATION_REQUIRED`.
- If confirmed, write `.env` and JSON metadata atomically or via temp file + replace.
- Never log raw secret values.

## Secret Resolver Contract
- Runtime resolves `api_key_env` or `password_env` from process environment or `.env` loader.
- Resolver returns secret only to backend provider/connection code.
- Resolver response to API/UI is masked status only.

## Masked Response Contract
Responses may include:
```json
{
  "profile_id": "local_postgres",
  "password_env": "SAFY_DB_LOCAL_POSTGRES_PASSWORD",
  "secret_configured": true,
  "secret_mask": "****"
}
```
Responses must not include `api_key`, `password`, or raw env values.

## Overwrite Confirmation Contract
If profile or env var exists, save endpoint returns:
```json
{
  "success": false,
  "data": {
    "profile_id": "local_postgres",
    "overwrite_required": true,
    "overwrite_target": "profile_and_env_var"
  },
  "error": {
    "code": "PROFILE_OVERWRITE_CONFIRMATION_REQUIRED",
    "message": "Profile or environment variable already exists.",
    "details": {}
  },
  "meta": {
    "request_id": "req_...",
    "timestamp": "..."
  }
}
```

## Permission Policy Notes
- Agent connected database path remains strict read-only.
- User query box is user-controlled and uses selected credential permission after safety check, confirmation, and audit.
- `manual_write_enabled` is metadata/UI warning only unless a future explicit policy enables blocking behavior.
