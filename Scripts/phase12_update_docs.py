from pathlib import Path

section = '''# SAFY Phase 12 Official Production Runtime — 2026-06-29

Status: The GPT-like Runtime Kernel is now the official production path.

Official runtime command:

```powershell
cd C:\\Users\\ASUS\\SAFY
$env:PYTHONNOUSERSITE = "1"
$env:PYTHONPATH = (Get-Location).Path
& "C:\\Program Files\\Python312\\python.exe" -m Apps.Api.safy_api.cli run --port 8000
```

Production ownership:
- `Apps/Api/safy_api/app_factory.py` creates the official FastAPI app used by the CLI.
- `Apps/Api/safy_api/main.py` is app wiring/compatibility only and imports the official app factory.
- Route-owner modules are primary for `/chat`, `/agent/chat`, `/query/check`, `/sandbox-rules/*`, `/runtime/health`, files, sessions, and auth/profile support.
- `Runtime/live_runtime.py` is the canonical Runtime Kernel owner for session, memory, sandbox, rules, skills, context builder, and event bus.
- `Runtime/meta.py` is removed; import scan for `Runtime.meta` is clean.
- `run_strict_runtime.py` is retained only as a dev/test harness; it is not the official production path.
- Dashboard assets are mounted by the official app and use relative API URLs on port 8000, not hardcoded 8100.

Safety invariants remain unchanged:
- AI drafts/plans/explains but never auto-executes real DB changes.
- Check Safety is required before Execute.
- User explicit Execute is required for real DB execution.
- Active sandbox rules affect SQL generation and deterministic safety checks.
- Rule conflicts are user-decision states; rules do not auto-modify real schema.
- Prompt/context files and sandbox rule files remain separate flows.
- Errors use SAFY JSON envelopes with request_id.

Phase 12 evidence:
- Final report: `Reports/SAFY_PHASE12_OFFICIAL_PRODUCTION_FINAL_REPORT_2026-06-29.md`
- UAT CSV: `Tests/SAFY_PHASE12_OFFICIAL_PRODUCTION_UAT_RESULTS_2026-06-29.csv`
- Evidence folder: `Tests/evidence/2026-06-29/phase12-official/`
'''

for name in ['SOUL.md', 'SAFY_source.md', 'current_state.md', 'README.md']:
    path = Path(name)
    if not path.exists():
        continue
    old = path.read_text(encoding='utf-8')
    marker = '# SAFY Phase 12 Official Production Runtime — 2026-06-29'
    if marker in old:
        old = old.split(marker, 1)[1]
        old = old[old.find('\n') + 1:] if '\n' in old else ''
    path.write_text(section + '\n---\n\n' + old, encoding='utf-8')
    print(path)
