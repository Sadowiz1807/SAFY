# Phase 8 UI Spec

Executed by main-agent only. No sub-agents used.

## UI goals

Phase 8 UI must let the user work with real connected databases in a clearly labeled read-only mode without confusing that mode with sandbox or mock connected preview behavior.

## Required panels and fields

### Real DB profile panel

Must show:

- connection status
- DBMS type
- redacted host
- database name
- read-only mode status
- profile identifier

Profile UI must not show raw passwords, raw DSNs, or raw tokens.

### Schema browser

Must show:

- schemas / databases
- tables
- columns
- data types
- primary keys
- foreign keys
- indexes
- views
- constraints
- comments / descriptions if available and redacted
- estimated row counts if available

Schema browser must not auto-fetch sample rows.

### Sample row approval UX

Must provide:

- explicit user action to request sample rows
- visible approval state
- capped sample size
- redaction indicators
- warning that sample rows are temporary and not stored in session history

### User SQL textbox

Must provide:

- dedicated real DB SQL input area
- explicit check action
- explicit `SELECT` execute action
- visible binding to the latest check result
- no implicit auto-run on paste or type

### Query preview

Must show:

- normalized SQL preview
- statement type
- risk / warning summary
- target database profile
- read-only enforcement state

### Confirmation modal for sensitive SELECT

Must show:

- why confirmation is required
- whether trigger came from sensitive table/column match, broad scan detection, row-limit policy, or sample-row policy
- confirmation expiry
- one-time nature of the confirmation

### Blocked operation panel

Must handle:

- `INSERT`
- write SQL
- destructive SQL
- multi-statement SQL
- `SELECT ... FOR UPDATE`
- unsafe side-effect SQL

Blocked-operation UX must:

- state clearly that Phase 8 is read-only
- show the SQL only as non-executed text if requested
- tell the user they must run blocked SQL outside SAFY if they still want it executed

### Result table

Must show:

- temporary result rows
- row count
- truncation status
- timeout status
- redaction status
- execution time
- audit ID or result trace reference if available

Temporary result display behavior:

- rows may be displayed for a limited period
- rows should disappear after the display period ends
- rows must not be written into session history by default

## Required mode distinction

UI must clearly distinguish all three modes:

- sandbox DB
- mock connected DB preview
- real connected DB read-only

Required indicators:

- mode badge
- mode banner text
- execution warning text specific to the selected mode

Real DB mode must be visually stronger than mock mode and must always show a warning banner.

## Real DB warning banner

Must communicate:

- user is connected to a real database
- Phase 8 permits read-only operations only
- unsafe SQL is blocked
- sensitive or broad reads may require confirmation
- results are temporary and may be redacted/truncated

## Rendering safety requirements

UI must not render:

- raw traceback
- raw driver errors
- raw credentials
- untrusted HTML

All untrusted text must use safe rendering and redacted error normalization before display.

## UX states

UI should define at least these states:

- disconnected
- testing connection
- connected read-only
- schema loading
- check pending
- confirmation required
- blocked
- executing read-only query
- results ready
- results expired / cleared
- connection error redacted

## Compatibility note

Because current Phase 7 UI still represents mock connected DB preview behavior, Phase 8 implementation must revise labels so the user cannot confuse mock preview with real connected read-only execution.
