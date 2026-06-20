# Phase 13 - v1.4.0 LLM Provider & Agent Runtime

Status: implemented for core/mock agent validation; real provider completion requires an available LM Studio/OpenAI-compatible endpoint with env gate enabled.

Security invariants: LLM proposes SQL only; SAFY validates with SQL Guard; execution remains bound to query_check -> query_execute; no raw API keys or result rows are persisted.

/query/check remains metadata/SQL Guard only. LLM output is never trusted. Writes, multi-statement SQL, bypass requests, direct execution, raw secrets, and row persistence are blocked by backend policy.
