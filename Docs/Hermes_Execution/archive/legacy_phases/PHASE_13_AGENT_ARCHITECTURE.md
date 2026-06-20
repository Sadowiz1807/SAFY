# Phase 13 - v1.4.0 LLM Provider & Agent Runtime

Status: implemented for core/mock agent validation; real provider completion requires an available LM Studio/OpenAI-compatible endpoint with env gate enabled.

Security invariants: LLM proposes SQL only; SAFY validates with SQL Guard; execution remains bound to query_check -> query_execute; no raw API keys or result rows are persisted.

AgentRuntime builds a fixed safety prompt with schema summary, calls the configured provider, parses structured JSON, sends SQL through QueryOrchestrator.check, and executes sandbox SELECTs only through QueryOrchestrator.execute.
