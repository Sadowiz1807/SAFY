# Hermes Conflict Policy

## Purpose
Define how Hermes handles conflicts between sub-agent work, user decisions, and `SAFY_source.md`.

## Conflict Handling Steps
1. Stop accepting the conflicted task output.
2. Identify exact files/sections involved.
3. Compare with `SAFY_source.md` and explicit user decisions.
4. Decide whether the resolution is a minor safer clarification or needs user decision.
5. Patch only after decision/validation.
6. Record conflict and resolution in the relevant core artifact if it changes a decision, or in Docs/Hermes_Execution/report/ when a report is needed.

## Hermes May Resolve Without Asking User If
- The resolution is stricter/safer.
- It does not change user-facing product behavior.
- It does not contradict explicit user decision.
- It does not weaken source security policy.

## Hermes Must Ask User If It Affects
- Agent database permissions.
- User query box permissions.
- Secret storage.
- UI flow.
- Profile save behavior.
- High-risk confirmation.
- Scope of v1.0.0.

## Known Stage 0 Additive Decisions
The Hermes plan adds details not explicit in `SAFY_source.md`:
- Chat-first + left sidebar + right sidebar UI.
- Right sidebar user query box flow.
- Backend-generated 4-digit confirmation code.
- Default e-commerce domain when domain missing.

These are treated as user decisions that extend planning docs, not as source-policy conflicts, because they do not weaken existing safety rules.
