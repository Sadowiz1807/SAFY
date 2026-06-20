# Phase 13 - v1.4.0 LLM Provider & Agent Runtime

Status: implemented for core/mock agent validation; real provider completion requires an available LM Studio/OpenAI-compatible endpoint with env gate enabled.

Security invariants: LLM proposes SQL only; SAFY validates with SQL Guard; execution remains bound to query_check -> query_execute; no raw API keys or result rows are persisted.

Run: python -m compileall LLM Agent Gateway Apps/Api/safy_api Apps/Web Tests/phase13 -q; python -m pytest Tests/phase13 -q -rs --ignore=tmp --basetemp=tmp/pytest_phase13; optional real provider gates with SAFY_REQUIRE_REAL_LLM_PROVIDER=1 or SAFY_REQUIRE_REAL_AGENT_RUNTIME=1 and provider env such as LMSTUDIO_BASE_URL/LMSTUDIO_MODEL, OPENAI_API_KEY/OPENAI_BASE_URL/OPENAI_MODEL, OPENROUTER_API_KEY/OPENROUTER_BASE_URL/OPENROUTER_MODEL, OLLAMA_BASE_URL/OLLAMA_MODEL/OLLAMA_API_KEY, or OPENAI_COMPAT_BASE_URL/OPENAI_COMPAT_MODEL/OPENAI_COMPAT_API_KEY.
