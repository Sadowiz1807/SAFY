# SAFY Secret Env + OpenRouter Fix Report

## Scope

Fixes only the two reported areas:

1. Save Database returned `SECRET_VALUE_REJECTED`.
2. OpenRouter/model provider connection failed when using a raw API key.

No unrelated UI descriptions were added back.

## Database Save fix

`/database-profiles` did endpoint-duplicate validation using the raw payload before the secret was moved into `.env`.

That could trigger `SECRET_VALUE_REJECTED` in stricter profile validation paths.

Now:

- endpoint duplicate checking uses a secret-stripped copy of the payload,
- Test Connection moves transient API key into `.env` for the local runtime without saving a DB profile,
- Save Database still stores only env references in JSON profiles,
- `_write_secret_to_env()` also hydrates `os.environ` so the current running process can use the key immediately.

## OpenRouter/model provider fix

The frontend was sending the raw API key in both:

```json
api_key
api_key_env
```

`api_key_env` is supposed to be an uppercase environment variable name, not the key value.

Now:

- frontend sends raw model key only as `api_key`,
- backend writes remote provider keys to `.env`,
- backend saves only `api_key_env`,
- OpenAI-compatible adapter can read from `os.environ` or `.env`,
- provider aliases accept `openai_compat` as `openai_compatible`.

## Files changed

- `Apps/Api/safy_api/main.py`
- `Apps/Web/safy-ui.js`
- `LLM/provider_adapters/openai_compatible.py`
- `LLM/provider_profiles.py`

## Validation

Passed:

```bash
python -m py_compile <all project .py files>
node --check Apps/Web/safy-ui.js
python import smoke for main/model adapter
functional smoke for raw DB key -> .env and raw OpenRouter key -> .env
```

## Final status

SAFY_SECRET_ENV_AND_OPENROUTER_FIXED
