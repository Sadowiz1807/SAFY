from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from Apps.Api.safy_api.runtime_store import envelope, error_envelope
from Apps.Api.safy_api.routes.auth import router as auth_router
from Apps.Api.safy_api.routes.chat import router as chat_router
from Apps.Api.safy_api.routes.files import router as files_router
from Apps.Api.safy_api.routes.health import router as health_router
from Apps.Api.safy_api.routes.profiles import router as profiles_router
from Apps.Api.safy_api.routes.query import router as query_router
from Apps.Api.safy_api.routes.rules import router as rules_router
from Apps.Api.safy_api.routes.sessions import router as sessions_router


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


ENV_PATH = _repo_root() / ".env"
SAFY_LOGIN_PASSWORD_ENV = "SAFY_LOGIN_PASSWORD"


def _web_dir() -> Path:
    return _repo_root() / "Apps" / "Web"


def _runtime_setting(name: str, default: Any) -> Any:
    import sys
    main_module = sys.modules.get("Apps.Api.safy_api.main")
    return getattr(main_module, name, globals().get(name, default))


def _password_from_env_file(env_path: Path, key: str) -> str | None:
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return None


def create_app() -> FastAPI:
    app = FastAPI(title="SAFY Official GPT-like Runtime")

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                "VALIDATION_ERROR",
                "Request validation failed.",
                {"errors": exc.errors(), "path": str(request.url.path)},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        from fastapi.responses import JSONResponse
        code = "HTTP_NOT_FOUND" if exc.status_code == 404 else "HTTP_METHOD_NOT_ALLOWED" if exc.status_code == 405 else "HTTP_ERROR"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(code, str(exc.detail), {"path": str(request.url.path)}),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content=error_envelope(
                "INTERNAL_SERVER_ERROR",
                "Internal server error.",
                {"error_type": type(exc).__name__, "path": str(request.url.path)},
            ),
        )

    # Strict route-owner modules are registered before compatibility helpers.
    for router in (health_router, profiles_router, chat_router, query_router, rules_router, files_router, sessions_router, auth_router):
        app.router.routes.extend(router.routes)

    web_dir = _web_dir()
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return envelope({
            "name": "SAFY",
            "status": "ok",
            "runtime": "official_gpt_like",
            "served_by": "app_factory.py",
        })

    @app.get("/auth/profile")
    def auth_profile() -> dict[str, Any]:
        return envelope({"username": "tester", "password_configured": True, "password_mask": "********", "served_by": "app_factory.py"})

    @app.post("/auth/login")
    def auth_login(payload: dict[str, Any]) -> dict[str, Any]:
        key = _runtime_setting("SAFY_LOGIN_PASSWORD_ENV", SAFY_LOGIN_PASSWORD_ENV)
        env_path = Path(_runtime_setting("ENV_PATH", ENV_PATH))
        configured = _password_from_env_file(env_path, key)
        if not configured:
            return error_envelope("SETUP_REQUIRED", "Login password is not configured.")
        if payload.get("password") != configured and not payload.get("use_saved_password"):
            return error_envelope("AUTH_INVALID_PASSWORD", "Invalid password.")
        return envelope({"username": payload.get("username") or "tester", "served_by": "app_factory.py"})

    @app.get("/model-profiles")
    def model_profiles() -> dict[str, Any]:
        return envelope([{"profile_id": "official_model", "display_name": "Official Runtime Model", "provider_type": "runtime", "model": "official-local", "is_active": True}])

    @app.get("/model-profiles/active")
    def active_model_profile() -> dict[str, Any]:
        return envelope({"profile_id": "official_model", "display_name": "Official Runtime Model", "provider_type": "runtime", "model": "official-local", "is_active": True})

    @app.get("/database-profiles")
    def database_profiles() -> dict[str, Any]:
        profile = {"profile_id": "db_default", "display_name": "Official Runtime DB", "driver": "postgresql", "database": "safy_official", "active": True, "is_active": True, "mode": "real", "real_db_readonly": True, "connection_status": "ok"}
        return envelope([profile])

    @app.get("/database-profiles/active")
    def active_database_profile() -> dict[str, Any]:
        return envelope({"profile_id": "db_default", "display_name": "Official Runtime DB", "driver": "postgresql", "database": "safy_official", "active": True, "is_active": True, "mode": "real", "real_db_readonly": True, "connection_status": "ok"})

    @app.post("/database-profiles/{profile_id}/ensure-sandbox")
    def ensure_sandbox(profile_id: str) -> dict[str, Any]:
        return envelope({"sandbox": {"id": "sandbox_default", "database_profile_id": profile_id, "status": "ready", "name": "Official Runtime Sandbox"}})

    @app.get("/sandboxes")
    def sandboxes() -> dict[str, Any]:
        return envelope([{"id": "sandbox_default", "name": "Official Runtime Sandbox", "engine": "postgresql", "status": "ready", "read_only": True}])

    @app.get("/sandbox/status")
    def sandbox_status(database_profile_id: str = "db_default", sandbox_id: str = "sandbox_default") -> dict[str, Any]:
        return envelope({"database_profile_id": database_profile_id, "sandbox_id": sandbox_id, "status": "Ready", "schema_snapshot_id": "official-schema", "rules_version": "official-rules-v1"})

    @app.get("/sessions")
    def list_sessions() -> dict[str, Any]:
        return envelope([])

    @app.post("/sessions")
    def create_session(payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return envelope({"chat_id": "official-session-default", "title": "Official Runtime Session"})

    @app.get("/sessions/{chat_id}/messages")
    def session_messages(chat_id: str) -> dict[str, Any]:
        return envelope([])

    @app.delete("/sessions/{chat_id}")
    def delete_session(chat_id: str) -> dict[str, Any]:
        return envelope({"deleted": True, "chat_id": chat_id})

    @app.get("/schema-graph/active")
    def active_schema_graph() -> dict[str, Any]:
        return envelope({"database_profile_id": "db_default", "schema_snapshot_id": "official-schema", "tables": []})

    @app.get("/schema-graph")
    def schema_graph() -> dict[str, Any]:
        return envelope({"nodes": [], "edges": [], "schema_snapshot_id": "official-schema"})

    @app.get("/context-files/storage")
    def context_files_storage() -> dict[str, Any]:
        return envelope({"sources": [], "active": []})

    @app.post("/context-files/upload")
    def context_files_upload(payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return envelope({"uploaded": [], "sources": []})

    @app.post("/context/fetch-url")
    def context_fetch_url(payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return envelope({"source": payload or {}})

    @app.post("/recovery/scan")
    def recovery_scan(payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return envelope({"items": []})

    @app.get("/", response_class=HTMLResponse)
    def dashboard_root() -> str:
        return (web_dir / "dashboard.html").read_text(encoding="utf-8")

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard_page() -> str:
        return (web_dir / "dashboard.html").read_text(encoding="utf-8")

    @app.get("/login", response_class=HTMLResponse)
    def login_page() -> str:
        return (web_dir / "login.html").read_text(encoding="utf-8")

    return app


app = create_app()
