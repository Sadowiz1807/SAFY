---
name: text_to_sql
version: 1.0.0
description: "Reference guidance for Vanna-style text-to-SQL systems."
enabled: true
risk_level: medium
references: ["references/vanna_repo_notes.md"]
---

# Text To Sql

## Purpose
Reference guidance for Vanna-style text-to-SQL systems.

## When to use
Use this skill when SAFY routes a user request to `text_to_sql` in the normal Perceive → Plan → Slot-fill → Route → Act → Verify → Present → Remember workflow.

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
Return the normal SAFY response envelope or action result for `text_to_sql`.

## Failure behavior
Fail closed with a clear error or clarification request. Do not run unsafe SQL or hidden actions.
