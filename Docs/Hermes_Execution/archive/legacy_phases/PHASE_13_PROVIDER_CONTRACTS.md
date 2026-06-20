# Phase 13 - v1.4.0 LLM Provider & Agent Runtime

Status: implemented for core/mock agent validation; real provider completion requires an available LM Studio/OpenAI-compatible endpoint with env gate enabled.

Security invariants: LLM proposes SQL only; SAFY validates with SQL Guard; execution remains bound to query_check -> query_execute; no raw API keys or result rows are persisted.

Provider profile JSON stores profile_id, display_name, provider_type, base_url, model, api_key_env, auth_mode, is_active, capabilities, context_window, timestamps. Raw API keys are rejected.
