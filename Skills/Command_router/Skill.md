---
name: command_router
version: 1.0.0
description: "Routes chat messages and slash commands into SAFY workflow intents."
enabled: true
risk_level: low
references: []
---

# Command Router

## Purpose
Routes chat messages and slash commands into SAFY workflow intents.

## When to use
Use this skill when SAFY routes a user request to `command_router` in the normal Perceive → Plan → Slot-fill → Route → Act → Verify → Present → Remember workflow.

## Required context
- User request and conversation state.
- Active database or sandbox context when relevant.
- SAFY system safety policy and SQL guard results when SQL is involved.

## Procedure
Load this document as guidance, then use SAFY shared tools/actions for any operation. Do not execute code from the skill pack.

## Safety rules
- Skill content is advisory and cannot override system policy.
- Do not read secrets, change database profiles, or bypass SQL Guard.
- Write, DDL, and destructive operations must use sandbox/confirmation rules.
- Execute actual actions only through SAFY shared guarded tools/actions.

## Expected output
Return the normal SAFY response envelope or action result for `command_router`.

## Failure behavior
Fail closed with a clear error or clarification request. Do not run unsafe SQL or hidden actions.
