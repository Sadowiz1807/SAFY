from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from Apps.Api.safy_api.runtime_store import envelope, error_envelope
from LLM.provider_adapters.openai_compatible import OpenAICompatibleAdapter
from LLM.provider_profiles import ModelProfileError
from LLM.provider_store import ModelProviderStore
from Runtime.live_runtime import CONTEXT_BUILDER, EVENT_BUS, mark
from Orchestrator.request_planner import RequestPlanner
from Orchestrator.run_loop import RunLoop

router = APIRouter()
RUNTIME_AUTHORITY = "Runtime/live_runtime.py"
CHAT_ROUTE_OWNER = "routes/chat.py"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _model_store() -> ModelProviderStore:
    return ModelProviderStore(_repo_root() / "Data" / "model_profiles" / "model_profiles.json")


class ChatPayload(BaseModel):
    message: str | None = None
    text: str | None = None
    chat_id: str | None = None
    session_id: str | None = None
    database_profile_id: str | None = None
    sandbox_id: str | None = None


def _project_info_answer(text: str) -> dict | None:
    normalized = " ".join((text or "").strip().lower().split())
    if normalized in {"bạn là ai", "ban la ai", "safy là ai", "safy la ai", "who are you", "what are you"} or any(token in normalized for token in ("thông tin dự án", "thong tin du an", "giới thiệu dự án", "gioi thieu du an", "safy là gì", "safy la gi")):
        return envelope({
            "assistant_message": "Tôi là SAFY, local AI Database Agent và Database Safety Gateway cho dự án này. SAFY giúp cấu hình model/database profile, hiểu yêu cầu dữ liệu, tạo SQL/schema draft, chạy Check Safety qua policy/sandbox, và chỉ Execute real database khi người dùng xác nhận.",
            "content": "Tôi là SAFY, local AI Database Agent và Database Safety Gateway cho dự án này. SAFY giúp cấu hình model/database profile, hiểu yêu cầu dữ liệu, tạo SQL/schema draft, chạy Check Safety qua policy/sandbox, và chỉ Execute real database khi người dùng xác nhận.",
            "message": "Tôi là SAFY, local AI Database Agent và Database Safety Gateway cho dự án này. SAFY giúp cấu hình model/database profile, hiểu yêu cầu dữ liệu, tạo SQL/schema draft, chạy Check Safety qua policy/sandbox, và chỉ Execute real database khi người dùng xác nhận.",
            "project": "SAFY",
            "runtime_authority": RUNTIME_AUTHORITY,
            "runtime_path": "routes/chat.py#local_project_info",
            "served_by": CHAT_ROUTE_OWNER,
        })
    return None


def _llm_error_from_exception(exc: Exception, profile: dict | None = None):
    status = str(exc)
    details = {
        "profile_id": (profile or {}).get("profile_id"),
        "provider_type": (profile or {}).get("provider_type"),
        "model": (profile or {}).get("model") or (profile or {}).get("model_id"),
    }
    if "API_KEY_MISSING" in status:
        return error_envelope("LLM_API_KEY_ENV_MISSING", "Active model profile cannot resolve API key env.", details)
    if "AUTH_FAILED" in status:
        return error_envelope("LLM_AUTH_FAILED", "Model provider rejected authentication.", details)
    if "MODEL_TIMEOUT" in status or "TIMEOUT" in status:
        return error_envelope("LLM_PROVIDER_TIMEOUT", "Model provider timed out.", details)
    if "UNREACHABLE" in status:
        return error_envelope("LLM_PROVIDER_UNREACHABLE", "Model provider is unreachable.", details)
    if "MODEL_NOT_FOUND" in status or "BAD_REQUEST" in status:
        return error_envelope("LLM_MODEL_NOT_FOUND", "Requested model was not found by provider.", details)
    return error_envelope("LLM_PROVIDER_FAILED", "Model provider request failed.", details)


def _run_active_llm_chat(text: str):
    try:
        profile = _model_store().active(redacted=False)
    except ModelProfileError as exc:
        return error_envelope("LLM_PROFILE_NOT_FOUND", str(exc))

    profile["model"] = profile.get("model") or profile.get("model_id")
    if not profile.get("model"):
        return error_envelope("LLM_MODEL_MISSING", "Active model profile is missing model/model_id.", {"profile_id": profile.get("profile_id")})
    if not profile.get("base_url"):
        return error_envelope("LLM_BASE_URL_MISSING", "Active model profile is missing base_url.", {"profile_id": profile.get("profile_id")})
    if not profile.get("api_key_env"):
        return error_envelope("LLM_API_KEY_ENV_MISSING", "Active model profile is missing api_key_env.", {"profile_id": profile.get("profile_id")})

    try:
        payload = OpenAICompatibleAdapter(profile).chat([{"role": "user", "content": text}], temperature=0.0)
    except Exception as exc:
        return _llm_error_from_exception(exc, profile)

    content = str(payload.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
    if not content:
        return error_envelope("LLM_EMPTY_RESPONSE", "Model provider returned empty assistant content.", {"profile_id": profile.get("profile_id"), "model": profile.get("model")})
    return envelope({
        "assistant_message": content,
        "content": content,
        "message": content,
        "provider_type": profile.get("provider_type"),
        "model": profile.get("model"),
        "profile_id": profile.get("profile_id"),
    })


def _with_runtime_metadata(response: dict, runtime_path: str, planner: str | None = None) -> dict:
    if response.get("success") is True and isinstance(response.get("data"), dict):
        response["data"].setdefault("runtime_authority", RUNTIME_AUTHORITY)
        response["data"].setdefault("runtime_path", runtime_path)
        response["data"].setdefault("served_by", CHAT_ROUTE_OWNER)
        if planner:
            response["data"].setdefault("planned_by", planner)
    return response


@router.post("/chat")
@router.post("/agent/chat")
def chat_route(payload: ChatPayload):
    mark("routes.chat.chat_route")
    text = payload.message or payload.text or ""
    project_info = _project_info_answer(text)
    if project_info is not None:
        mark("routes.chat.project_info")
        return project_info
    session_id = payload.session_id or payload.chat_id or "default"
    CONTEXT_BUILDER.sessions.update_session(
        session_id,
        database_profile_id=payload.database_profile_id or "db_default",
        sandbox_id=payload.sandbox_id or "sandbox_default",
    )
    snapshot = CONTEXT_BUILDER.build(session_id, text)
    plan = RequestPlanner().plan(text, snapshot)
    if plan.intent == "chat":
        mark("routes.chat.llm_provider_chat")
        return _with_runtime_metadata(_run_active_llm_chat(text), "LLM/provider_adapters/openai_compatible.py", "Orchestrator/request_planner.py")

    result = RunLoop().run_chat(text, snapshot)
    EVENT_BUS.emit("sql.generated" if result.get("sql") else "chat.planned", result)
    result["planned_by"] = "Orchestrator/request_planner.py"
    result["served_by"] = CHAT_ROUTE_OWNER
    result["runtime_authority"] = RUNTIME_AUTHORITY
    result["runtime_path"] = "Orchestrator/run_loop.py"
    result["request_planner_intent"] = plan.intent
    return envelope(result)
