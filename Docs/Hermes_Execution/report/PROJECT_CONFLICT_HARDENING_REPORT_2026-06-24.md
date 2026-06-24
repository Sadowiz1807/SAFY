# SAFY — Project Conflict Hardening Report

**Date:** 2026-06-24  
**Scope:** Resolve the project conflicts found in the `SAFY (2).zip` snapshot without changing SAFY's database safety boundaries.  
**Result:** `PASS WITH ONE-TIME GIT INDEX MIGRATION STEP`

## 1. Resolved conflicts

### Canonical skill paths

The source tree uses canonical paths:

```text
Skills/<lowercase_name>/SKILL.md
```

The `schema_graph` skill now includes the validator-required sections:

```text
## Required context
## Expected output
```

`python Scripts/validate_skills.py` passes for all 11 skills.

Because a Windows Git index may still track legacy case-only paths such as `Skills/Schema_graph/Skill.md`, the repository now includes:

```text
Scripts/normalize_skill_git_case.ps1
```

Run it once before the next commit if `git ls-files Skills` still shows legacy casing. It temporarily disables Git case folding, stages canonical skill paths, then restores the previous `core.ignorecase` value.

### Wheel/package resources

`pyproject.toml` now packages the runtime resources required outside an editable source checkout:

- `Configs/`
- `Apps/Web/`
- `Skills/`
- `DomainIntelligence/packs/`
- Domain Intelligence reports and metadata required by the installed runtime

The required resource directories are installable packages through minimal `__init__.py` markers.

A built wheel was installed into an isolated target outside the repository. The installed runtime:

- imported the FastAPI app;
- resolved bundled web assets;
- loaded 10 domain packs;
- passed `domain list`;
- passed `domain validate --all` with 10/10 packs valid.

### Canonical project state

`current_state.md` is no longer ignored by Git and has been updated with:

- canonical skill casing;
- skill validator status;
- non-editable wheel verification;
- clean handoff packaging behavior;
- current 8-test count;
- the one-time Git case migration requirement;
- the current packaging threshold of 20 files.

### Safe handoff packaging

A canonical packager was added:

```powershell
python Scripts/package_clean_handoff.py
```

It excludes:

- `.git/`;
- `.env` and local environment variants, except explicit templates/examples;
- credentials and secret stores;
- database/model/user runtime profiles;
- sessions, audit databases, sandboxes, logs, caches, bytecode, build directories, and egg metadata.

Validation created a clean archive containing 1,094 files and excluding 1,462 runtime/generated files. No forbidden secret/runtime paths were found in the resulting ZIP.

### Line-ending conflict containment

`.gitattributes` now preserves committed bytes instead of triggering an unrelated repository-wide LF/CRLF renormalization. Windows command scripts remain explicitly CRLF. This prevents automatic mass line-ending churn during the next functional commit.

### Report conflict

The pre-fix `SAFY_NGHIEM_THU_RASOAT_DOMAIN_INTELLIGENCE_2026-06-24.md` report is explicitly marked `SUPERSEDED / HISTORICAL`, so agents do not treat its old `KHÔNG ĐẠT` result as current project state.

## 2. Files changed

1. `.gitignore`
2. `.gitattributes`
3. `Apps/__init__.py`
4. `Apps/Api/__init__.py`
5. `Configs/__init__.py`
6. `Skills/__init__.py`
7. `pyproject.toml`
8. `Skills/schema_graph/SKILL.md`
9. `Scripts/normalize_skill_git_case.ps1`
10. `Scripts/package_clean_handoff.py`
11. `Tests/test_project_packaging.py`
12. `current_state.md`
13. `SAFY_source.md`
14. `Docs/Hermes_Execution/report/SAFY_NGHIEM_THU_RASOAT_DOMAIN_INTELLIGENCE_2026-06-24.md`
15. `Docs/Hermes_Execution/report/PROJECT_CONFLICT_HARDENING_REPORT_2026-06-24.md`

## 3. Validation evidence

```text
python Scripts/validate_skills.py
PASS — 11 skills

python -m compileall -q DomainIntelligence Core Agent Apps/Api/safy_api Tests Scripts
PASS

python -m pytest -q
8 passed in 1.63s

node --check Apps/Web/dashboard.js
PASS

node --check Apps/Web/schema-graph.js
PASS

node --check Apps/Web/login.js
PASS

python -m pip wheel . --no-deps
PASS

isolated installed-target FastAPI import
PASS

isolated installed-target DomainRegistry
PASS — 10 packs

isolated installed-target domain validate --all
PASS — 10/10 valid

python Scripts/package_clean_handoff.py
PASS

clean handoff forbidden-path scan
PASS

git check-ignore current_state.md
not ignored — PASS
```

## 4. Important commit note

Source files are corrected, but a Git index cannot be rewritten by copying a patch into an existing Windows repository. Before committing, run:

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\normalize_skill_git_case.ps1
python Scripts\validate_skills.py
```

Then inspect:

```powershell
git diff --cached --name-status -- Skills
```

The staged output should show case-only renames from legacy capitalized directories and `Skill.md` to canonical lowercase directories and `SKILL.md`.

Do not run `git add --renormalize .` as part of this feature commit.

## 5. Final status

```text
Skill source contract: PASS
Skill cross-platform casing source: PASS
Windows Git index migration helper: READY
Wheel package resources: PASS
Installed wheel runtime: PASS
Domain packs: 10/10 PASS
Canonical current_state tracking: PASS
Clean handoff safety: PASS
Line-ending mass-churn prevention: PASS
Current automated tests: 8/8 PASS
```
