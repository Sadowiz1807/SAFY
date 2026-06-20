# Phase 13 - v1.4.0 LLM Provider & Agent Runtime

Status: implemented for core/mock agent validation; real provider completion requires an available LM Studio/OpenAI-compatible endpoint with env gate enabled.

Security invariants: LLM proposes SQL only; SAFY validates with SQL Guard; execution remains bound to query_check -> query_execute; no raw API keys or result rows are persisted.

Minimal UI requirement remains staged in the current web shell: provider settings, active provider indicator, target indicator, generated SQL preview, check/execute result, and block reason display should call the Phase 13 APIs.
