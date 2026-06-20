# Phase 4 Validation Checklist

## Planning Gate

- [x] Source docs read.
- [x] Phase 3 PASS boundary preserved.
- [x] Task board placeholder identified as non-dispatchable.
- [x] Connected DB execution deferred.
- [x] Sub-agent implementation dispatch blocked.

## Implementation Gate For Future Phase 4

- [ ] `Core/` Agent Core modules exist.
- [ ] `Providers/` registry, model client, mock provider exist.
- [ ] `Skills/Create_database/Skill.md` exists.
- [ ] `SkillPolicy` compiler exists and is tested.
- [ ] `Tools/` registry/executor exists and denies unknown tools.
- [ ] `/agent/chat` performs real orchestration using mock provider first.
- [ ] Create database prompt defaults to e-commerce if domain missing and states assumption.
- [ ] Generated SQL is validated by SQL Guard before sandbox execution.
- [ ] Sandbox workspace is created and schema readback succeeds.
- [ ] UI technical result contains workflow id, workspace id, schema summary, risk level, and validation status.
- [ ] Connected database execution remains disabled in Phase 4 tests.
- [ ] Raw secrets do not appear in response/log/audit/provider prompt.
- [ ] Regression tests for Phases 1-3 still pass.

## Required Future Tests

- Unit: provider registry and mock provider.
- Unit: intent detector and default e-commerce assumption.
- Unit: Skill loader/router and SkillPolicy deny cases.
- Unit: ToolExecutor blocks unknown/bypassing tools.
- Unit: SQL Guard is called for every SQL execution.
- Integration: `/agent/chat` create database sandbox success.
- Integration: connected DB create prompt is blocked.
- Security: prompt injection cannot alter allowed tools.
- Security: secret redaction scan.
