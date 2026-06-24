# Validators

Validator implementations should be added later. A validator must:

1. Validate JSON schemas.
2. Confirm tables/columns exist in the logical schema.
3. Parse SQL using the declared dialect.
4. Execute SQL on a disposable target when practical.
5. Verify risk and route labels.
6. Reject secrets, real credentials, production rows, and PII.
7. Never write to SAFY's real connected database.
