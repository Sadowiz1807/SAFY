# Phase 13 - v1.4.0 LLM Provider & Agent Runtime

Status: implemented for core/mock agent validation; real provider completion requires an available LM Studio/OpenAI-compatible endpoint with env gate enabled.

Security invariants: LLM proposes SQL only; SAFY validates with SQL Guard; execution remains bound to query_check -> query_execute; no raw API keys or result rows are persisted.

Implemented endpoints: POST/GET/PATCH/DELETE /model-profiles, POST /model-profiles/{id}/test, POST /model-profiles/{id}/activate, POST /model-profiles/detect-local, POST /agent/chat, POST /agent/generate-sql, POST /agent/explain-result.
