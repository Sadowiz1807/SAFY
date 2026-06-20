# Phase 1 API Mock Spec - Contract-first Foundation

Source of truth: `C:/Users/ASUS/SAFY/Docs_prior_project/SAFY_source.md`

Status: historical Phase 1 planning contract. Phase 1 gate reports record completed mock/skeleton work; this artifact remains the contract reference and does not authorize real LLM, sandbox, or database execution.

## Backend Mock Scope
Create FastAPI skeleton, Pydantic schemas, common response/error envelope, and mock endpoint behavior for Phase 1 only. No real SQL execution, real LLM execution, or real sandbox execution is required.

## Required Mock Endpoints
- `GET /profiles`
- `GET /sandbox/health`
- `POST /chat/new`
- `POST /agent/chat`
- `POST /query/check`
- `POST /query/execute`
- `POST /profiles/model/save`
- `POST /profiles/model/test`
- `POST /profiles/database/save`
- `POST /profiles/database/test`

## Endpoint Requirements
### GET /profiles
Returns model and database profile mock data with masked secret status only. No raw keys/passwords.

### GET /sandbox/health
Returns mock `healthy`, `docker_available`, and `sqlite_runner_available`.

### POST /chat/new
Returns `chat_id` and active status.

### POST /agent/chat
Returns mock assistant answer, generated SQL, schema summary, workflow status, and technical output. Default domain is e-commerce when no domain is provided. Agent connected DB remains read-only.

### POST /query/check
Must never execute SQL. Returns Safety Report. SELECT returns low-risk report. DELETE/DROP/UPDATE/ALTER returns high-risk report with visible 4-digit backend-generated numeric `confirmation_code`.

### POST /query/execute
Requires valid `check_id`, Yes decision, and valid code for high-risk checks. Reject missing check, missing code, invalid code, expired code, SQL mismatch, target mismatch, and permission denial.

### POST /profiles/model/save
Accepts raw `api_key` in request, writes raw secret only via `.env` writer contract, writes `api_key_env` to JSON, returns masked response. Existing profile/env var requires confirmation.

### POST /profiles/model/test
Tests using resolved secret in backend; response must not include raw secret.

### POST /profiles/database/save
Accepts raw DB password in request, writes raw secret only via `.env` writer contract, writes `password_env` to JSON, returns masked response. Existing profile/env var requires confirmation.

### POST /profiles/database/test
Tests using resolved secret in backend; response must not include raw password.

## Mock Error Behaviors
- Missing check id -> `QUERY_CHECK_REQUIRED`.
- Expired check -> `QUERY_CHECK_EXPIRED`.
- Missing Yes decision -> `USER_DECISION_REQUIRED`.
- Missing code -> `CONFIRMATION_CODE_REQUIRED`.
- Invalid code -> `CONFIRMATION_CODE_INVALID`.
- Expired code -> `CONFIRMATION_CODE_EXPIRED`.
- Credential permission failure -> `DB_PERMISSION_DENIED`.
- Existing profile without confirmation -> `PROFILE_OVERWRITE_CONFIRMATION_REQUIRED`.
