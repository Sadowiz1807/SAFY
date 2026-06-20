# Phase 9 Launcher Design

## Goal

The command below must work from outside the repository:

```powershell
cd C:\Users\ASUS
safy run
```

It must start the SAFY backend, serve the dashboard, and open the dashboard in the default browser unless disabled.

## Preferred Packaging Design

Use a Python console script if repository packaging supports it safely:

```toml
[project.scripts]
safy = "Apps.Api.safy_api.cli:main"
```

Required install flow:

```powershell
cd C:\Users\ASUS\SAFY
pip install -e .
cd C:\Users\ASUS
safy run
```

## Planned CLI Commands

- `safy run`
- `safy run --host 127.0.0.1 --port 8000`
- `safy run --no-reload`
- `safy run --browser`
- `safy run --no-browser`
- `safy info`
- `safy test`
- `safy test --phase phase9`

Default browser behavior: auto-open enabled.

## Repo Root Resolution

The CLI should resolve the package file location and derive the repository root from the installed editable package, not from process CWD. It should pass deterministic app/config/data paths into runtime setup.

## Uvicorn Invocation

Plan either `uvicorn.run("Apps.Api.safy_api.main:app", host=..., port=..., reload=...)` with an explicit app dir/root, or subprocess invocation with sanitized environment. Reload should be enabled by default for dev only if safe; `--no-reload` disables it.

## CWD Independence

All config/data/static paths must be resolved relative to repo root or an explicit `SAFY_HOME`, never `Path.cwd()`. Validation must run from `C:\Users\ASUS`.

## Browser Auto-open

After server startup readiness, open `http://127.0.0.1:8000/` using Python `webbrowser.open`. `--no-browser` suppresses this. `--browser` can force browser behavior if defaults change.

## Config and Env Paths

Config defaults should resolve to `Configs/app.yaml` and `Configs/toolsets.yaml` under repo root. Data defaults should resolve to `Data/`. `.env` support, if used, must not persist raw secrets into JSON stores.

## Tests

Validate from `C:\Users\ASUS`: `safy info`, `safy run --host 127.0.0.1 --port 8000 --no-browser`, health endpoint, dashboard root, docs route, and clean shutdown.

## Fallback Plan

If console scripts are too risky, plan `Scripts/safy.cmd`, `Scripts/safy.ps1`, and `Scripts/install_safy_launcher.ps1` as explicit launch wrappers. Preferred remains the Python console entry point.
