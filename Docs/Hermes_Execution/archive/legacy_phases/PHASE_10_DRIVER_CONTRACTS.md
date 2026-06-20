# Phase 10 Driver Contracts

Drivers live under `Gateway/db_drivers`.

Required interface:

```text
test_connection(profile, secret_context)
get_schema(profile, secret_context, options=None)
execute_readonly(sql, profile, secret_context, options=None)
```

Successful envelopes include `success`, `driver`, `database_profile_id`, `metadata`, and `warnings`. Query responses may include temporary `rows`; storage layers must strip rows. Errors use redacted `error_code`, `message`, and `details`.
