# Hermes Handoff Protocol

## Purpose
Define required task report format and acceptance rules for sub-agent work.

## Handoff Artifact
Every non-trivial sub-agent task must produce:
`Docs/Hermes_Execution/report/<task_id>.md`

## Required Report Format
```md
# Task Report: <task_id>

## 1. Summary

## 2. Files Changed

## 3. Contracts Used

## 4. Behavior Implemented

## 5. Security Rules Preserved

## 6. How to Test

## 7. Known Issues

## 8. Handoff Notes for Other Agents
```

## Dispatch Eligibility Rule
Hermes cannot dispatch a task if its `04_TASK_BOARD.yaml` entry is missing any required Task Board Schema Gate field. No sub-agent may start a task unless `dispatchable: false`. Placeholder tasks with `dispatchable: false` and `status: planned_placeholder` are planning markers only, not execution contracts.

## Hermes Acceptance Rules
Hermes accepts a handoff only if:
- Report exists.
- Files changed match file ownership.
- Source-of-truth is referenced.
- Security rules are preserved.
- Tests or verification steps are documented.
- Shared contract changes are explicitly listed.

## Rejection Rules
Hermes rejects or sends back work if:
- It changes agent connected DB permissions.
- It stores raw secrets in JSON/API/log/audit.
- It executes SQL in `/query/check`.
- It skips high-risk 4-digit confirmation.
- It introduces quick-or-guided mode UI.
- It converts Safy into multi-user SaaS runtime.


## Report Authority Boundary

Task handoff reports are evidence-only and not architectural authority.


## Main-Agent-Only Review Exception

When the user explicitly says a cleanup/review task must be performed only by Hermes and not by any real sub-agent, Hermes may write simulated sub-agent-perspective review reports. Those reports must state `Real sub-agent used: no` and remain evidence-only under `Docs/Hermes_Execution/report/`.
