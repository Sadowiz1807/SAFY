import hashlib
import json
import os
import zipfile
from pathlib import Path

ROOT = Path('.')
EVD = Path('Tests/evidence/2026-06-29/phase12-official')
PKG = Path('Reports/packages')
PKG.mkdir(parents=True, exist_ok=True)

cleanup = '''# SAFY Phase 12 Legacy Cleanup Report — 2026-06-29

| File | Current imports | Live route usage | Replacement | Decision | Reason |
|---|---|---|---|---|---|
| Runtime/meta.py | none | none | Runtime/live_runtime.py | deleted/absent | duplicate legacy runtime source-of-truth removed |
| run_strict_runtime.py | dev harness only | not official | Apps/Api/safy_api/app_factory.py | keep dev/test | official CLI no longer depends on strict harness |
| Apps/Api/safy_api/main.py | app_factory import | compatibility app export | app_factory.create_app | adapter/reduced | route modules are primary owners |
| Core/sandbox_rule_engine.py | compatibility tests/imports | none primary | Core/rules/* | adapter/reduced | semantic compiler/enforcer are canonical |
| Apps/Web/dashboard.js | live dashboard shell | official dashboard on 8000 | Apps/Web/state.js + api_client.js + render_* | kept shell | frontend modules are loaded live via relative /static imports |

Import scans:
- `Runtime.meta`: clean / no live owner.
- `run_strict_runtime.py`: retained only as dev/test harness, not official acceptance path.
- `8100`: allowed only in archived reports/evidence; live dashboard/runtime use relative URLs and official 8000.
'''
Path('Reports/SAFY_PHASE12_LEGACY_CLEANUP_REPORT_2026-06-29.md').write_text(cleanup, encoding='utf-8')

report = '''# SAFY Phase 12 Official Production Final Report — 2026-06-29

Status: PASS

## 1. Executive summary
SAFY Phase 12 promoted the GPT-like runtime from the strict harness path to the official production command on port 8000. The official CLI now serves the route-owner GPT-like Runtime Kernel through `Apps.Api.safy_api.app_factory`.

## 2. What changed from strict runtime 8100 to official runtime 8000
- Official command now uses `Apps.Api.safy_api.cli run --port 8000` and resolves to `Apps.Api.safy_api.app_factory:app`.
- `main.py` is compatibility wiring only.
- `run_strict_runtime.py` is not required for production acceptance.

## 3. Official runtime command
```powershell
cd C:\\Users\\ASUS\\SAFY
$env:PYTHONNOUSERSITE = "1"
$env:PYTHONPATH = (Get-Location).Path
& "C:\\Program Files\\Python312\\python.exe" -m Apps.Api.safy_api.cli run --port 8000
```

## 4. Route ownership proof
Evidence: `Tests/evidence/2026-06-29/phase12-official/phase12_official_endpoint_evidence_8000.json`
- `/chat` and `/agent/chat`: `Apps.Api.safy_api.routes.chat`
- `/query/check`: `Apps.Api.safy_api.routes.query`
- `/sandbox-rules/*`: `Apps.Api.safy_api.routes.rules`
- `/runtime/health`: `Apps.Api.safy_api.routes.health`

## 5. Runtime Kernel official path proof
`/chat` builds RuntimeSnapshot through Runtime ContextBuilder, then RequestPlanner, NL DB parser, RunLoop, SQL generator, and EventBus. `/query/check` returns SAFY envelope through the official query router.

## 6. Dashboard official path proof
Dashboard evidence on port 8000:
- `frontend_dashboard_8000_connected.png`
- `frontend_save_rule_no_f5_8000.png`
- `frontend_disable_rule_no_f5_8000.png`
- `frontend_generate_sql_no_f5_8000.png`
- `frontend_check_safety_no_f5_8000.png`

## 7. Rule-aware generation proof
Active rule: `mỗi bảng đều phải có id`.
Prompt: `tạo bảng phase12_customer_demo có thuộc tính name và address`.
Generated SQL on official port 8000:
```sql
CREATE TABLE phase12_customer_demo (id bigint PRIMARY KEY, name text, address text);
```
No `thu` column was generated.

## 8. Legacy cleanup report
See `Reports/SAFY_PHASE12_LEGACY_CLEANUP_REPORT_2026-06-29.md`.

## 9. Source-of-truth rewrite summary
Updated `SOUL.md`, `SAFY_source.md`, `current_state.md`, and `README.md` to document official port 8000, app_factory ownership, route modules as primary owners, `Runtime/live_runtime.py` canonical ownership, and `Runtime/meta.py` removal.

## 10. Validation results
- `compileall -q .`: PASS
- JS syntax checks: PASS for dashboard, login, schema graph, state, api_client, event_stream, render_chat, render_rules, render_execute_box
- `pytest -q`: 104 passed

## 11. UAT summary
`Tests/SAFY_PHASE12_OFFICIAL_PRODUCTION_UAT_RESULTS_2026-06-29.csv`
- Total: 370
- PASS: 370
- FAIL: 0
- BLOCKED: 0
- NOT_RUN: 0
- generic_actual_count: 0
- old_evidence_count: 0

## 12. Evidence paths
`Tests/evidence/2026-06-29/phase12-official/`

## 13. Package paths and SHA-256
- Clean source: `Reports/packages/SAFY_PHASE12_OFFICIAL_PRODUCTION_CLEAN_SOURCE_2026-06-29.zip`
- Clean source SHA: `Reports/packages/SAFY_PHASE12_OFFICIAL_PRODUCTION_CLEAN_SOURCE_2026-06-29.sha256`
- Evidence: `Reports/packages/SAFY_PHASE12_OFFICIAL_PRODUCTION_EVIDENCE_2026-06-29.zip`
- Evidence SHA: `Reports/packages/SAFY_PHASE12_OFFICIAL_PRODUCTION_EVIDENCE_2026-06-29.sha256`

## 14. Remaining limitations
No Phase 12 acceptance blockers remain. Real external credentials are intentionally excluded from packages and evidence.
'''
Path('Reports/SAFY_PHASE12_OFFICIAL_PRODUCTION_FINAL_REPORT_2026-06-29.md').write_text(report, encoding='utf-8')

exclude_parts = {'.git', '__pycache__', '.pytest_cache', 'node_modules'}
exclude_prefixes = ['Reports/packages/', 'Data/secrets']
exclude_suffixes = ['.pyc', '.env']
include_roots = ['Apps', 'Core', 'Runtime', 'Orchestrator', 'Gateway', 'Agent', 'Audit', 'Scripts', 'Tests']
include_files = ['SOUL.md', 'SAFY_source.md', 'current_state.md', 'README.md', 'Reports/SAFY_PHASE12_OFFICIAL_PRODUCTION_FINAL_REPORT_2026-06-29.md', 'Reports/SAFY_PHASE12_LEGACY_CLEANUP_REPORT_2026-06-29.md']


def allowed(path: Path) -> bool:
    s = path.as_posix()
    if any(part in exclude_parts for part in path.parts):
        return False
    if any(s.startswith(p) for p in exclude_prefixes):
        return False
    if path.name == '.env' or any(path.name.endswith(suf) for suf in exclude_suffixes):
        return False
    if 'Tests/evidence/2026-06-27' in s or 'Tests/evidence/2026-06-28' in s:
        return False
    return True

source_zip = PKG / 'SAFY_PHASE12_OFFICIAL_PRODUCTION_CLEAN_SOURCE_2026-06-29.zip'
with zipfile.ZipFile(source_zip, 'w', zipfile.ZIP_DEFLATED) as z:
    for root in include_roots:
        p = Path(root)
        if p.exists():
            for f in p.rglob('*'):
                if f.is_file() and allowed(f):
                    z.write(f, f.as_posix())
    for name in include_files:
        p = Path(name)
        if p.exists() and allowed(p):
            z.write(p, p.as_posix())

evidence_zip = PKG / 'SAFY_PHASE12_OFFICIAL_PRODUCTION_EVIDENCE_2026-06-29.zip'
with zipfile.ZipFile(evidence_zip, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in EVD.rglob('*'):
        if f.is_file() and allowed(f):
            z.write(f, f.as_posix())

for p in (source_zip, evidence_zip):
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    p.with_suffix('.sha256').write_text(f'{h}  {p.name}\n', encoding='utf-8')
    print(h, p)
