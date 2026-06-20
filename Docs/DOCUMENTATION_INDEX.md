# SAFY Documentation Index

**Status:** CURRENT

This index labels SAFY documentation so agents and contributors do not follow stale phase notes by accident.

## CURRENT

- `Docs/SAFY_CURRENT_PROJECT_STATUS.md` — canonical current project status, architecture, policy, compatibility, test matrix, and roadmap.
- `Docs/SAFY_AGENT_WORKFLOW_ARCHITECTURE.md` — current Hermes-inspired workflow architecture notes.
- `Docs/SAFY_TOOL_REGISTRY_AND_REVIEWERS.md` — current tool registry and deterministic reviewer notes.
- `README.md` — entrypoint and run instructions; defer to `Docs/SAFY_CURRENT_PROJECT_STATUS.md` for current architecture details.

## TARGET / SPEC

- `Safy_Docs/00_PROJECT_CONTEXT.md`
- `Safy_Docs/01_ARCHITECTURE.md`
- `Safy_Docs/02_API_SPEC.md`
- `Safy_Docs/03_DATA_SCHEMA.md`
- `Safy_Docs/04_CONFIG_SPEC.md`
- `Safy_Docs/05_SECURITY_POLICY.md`
- `Safy_Docs/06_DATABASE_DESIGN_POLICY.md`
- `Safy_Docs/07_DOMAIN_RULE_PACKS.md`
- `Safy_Docs/08_SKILLS_SPEC.md`
- `Safy_Docs/09_TOOLS_SPEC.md`
- `Safy_Docs/10_RUNTIME_AND_SANDBOX_SPEC.md`

These files describe intended design/spec areas. When they conflict with current runtime behavior, resolve against `Docs/SAFY_CURRENT_PROJECT_STATUS.md` first.

## PROCESS / PATCH HISTORY

- `Docs/Hermes_Execution/` — implementation process docs, handoff protocol, validation gates, conflict policy, task board, and patch reports.
- `Docs/Hermes_Execution/report/` — patch reports. These are historical evidence, not canonical runtime docs.
- `Docs/Hermes_Execution/archive/` — legacy phase notes.

## Documentation rule

Every new doc should include one of these labels near the top:

```text
CURRENT
TARGET
LEGACY
ARCHIVE
PROCESS
PATCH_REPORT
```
