# Hermes Phase Plan

## Purpose
Define dependency gates for Safy implementation. Phases are not calendar dates.

## Phase 0: Context Loading and Contract Freeze
Outputs: Hermes execution docs, roster, ownership, task board, validation gates, conflict policy.
Gate: all responsibilities clear; user decisions preserved; source-of-truth acknowledged.

## Phase 1: Contract-first Foundation
Outputs: mock API contracts, chat-first UI shell, profile/query mock flows.
Gate: UI runs with mock API; no raw secret returned; API format valid.

## Phase 2: Runtime, Profiles, Secrets, and Audit Base
Outputs: real profile storage, `.env` secret persistence, runtime/audit DB base.
Gate: JSON stores only env refs; overwrite confirmation works; logs redact secrets; migrations pass.

## Phase 3: SQL Guard, Tool System, Sandbox, and Query Safety Pipeline
Outputs: SQL parser/classifier/risk analyzer, tools, sandbox, `/query/check`, `/query/execute`.
Gate: SELECT works; high-risk requires 4-digit code; wrong code blocks; agent path read-only.

## Phase 4: Agent Core, Skills, Provider, and Create Database Workflow
Outputs: provider system, skills, SkillPolicy, real `/agent/chat`, create DB in sandbox.
Gate: create database prompt produces sandbox schema and UI technical result.

## Phase 5: Connected DB Read-only Agent Query and User Query Execution
Outputs: agent read-only connected DB path and user-controlled credential-based execution path.
Gate: agent destructive connected DB prompt blocked; user DML/DDL requires check/code/audit.

## Phase 6: Recovery, Session History, and Workspace Management
Outputs: session history, recovery, workspace ownership transfer, cleanup.
Gate: recover workspace works and old chat cannot execute into transferred workspace.

## Phase 7: Final Integration and Hardening
Outputs: full MVP validation and optional gate report under Docs/Hermes_Execution/report/.
Gate: all user decisions implemented or explicitly pending; no source policy violation.
