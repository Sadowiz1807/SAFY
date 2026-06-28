from __future__ import annotations

from typing import Any
import json
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_REQUEST_TIMEOUT_SECONDS = 180
DEFAULT_MAX_PAYLOAD_BYTES = 900_000
DEFAULT_MAX_MESSAGE_CHARS = 240_000


class OpenAICompatibleAdapter:
    def __init__(self, profile: dict[str, Any], timeout: int | None = None):
        self.profile = profile
        self.timeout = int(timeout or profile.get("request_timeout_seconds") or profile.get("timeout_seconds") or DEFAULT_REQUEST_TIMEOUT_SECONDS)
        self.base_url = profile["base_url"].rstrip("/")
        self.model = profile["model"]

    def _dotenv_value(self, key: str) -> str | None:
        if not key:
            return None
        candidates = []
        if os.environ.get("SAFY_HOME"):
            candidates.append(Path(os.environ["SAFY_HOME"]) / ".env")
        candidates.append(Path.cwd() / ".env")
        for env_path in candidates:
            try:
                if not env_path.exists():
                    continue
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    if not line or line.strip().startswith("#") or "=" not in line:
                        continue
                    name, value = line.split("=", 1)
                    if name.strip() == key:
                        return value.strip()
            except OSError:
                continue
        return None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.profile.get("auth_mode") == "env_api_key":
            env_name = self.profile.get("api_key_env") or ""
            key = os.environ.get(env_name) or self._dotenv_value(env_name)
            if not key:
                raise RuntimeError("BLOCKED_LLM_API_KEY_MISSING")
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def _redacted_error_body(self, exc: urllib.error.HTTPError, limit: int = 500) -> str:
        try:
            body = exc.read().decode("utf-8", errors="ignore")[:limit]
        except Exception:
            return ""
        for token in ("api_key", "authorization", "bearer", "password", "secret"):
            body = body.replace(token, "[redacted]")
        return body

    def _validate_chat_payload(self, payload: dict[str, Any]) -> None:
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            raise RuntimeError("LLM_PAYLOAD_INVALID: messages must be a non-empty list")
        total_chars = 0
        for index, message in enumerate(messages):
            if not isinstance(message, dict):
                raise RuntimeError(f"LLM_MESSAGE_CONTENT_INVALID: message[{index}] is not an object")
            role = message.get("role")
            if role not in {"system", "user", "assistant", "tool"}:
                raise RuntimeError(f"LLM_MESSAGE_CONTENT_INVALID: unsupported role {role!r}")
            content = message.get("content")
            if not isinstance(content, str):
                raise RuntimeError(f"LLM_MESSAGE_CONTENT_INVALID: message[{index}].content must be a string")
            total_chars += len(content)
        if total_chars > DEFAULT_MAX_MESSAGE_CHARS:
            raise RuntimeError(f"LLM_CONTEXT_TOO_LARGE: message chars {total_chars} exceed {DEFAULT_MAX_MESSAGE_CHARS}")
        body_size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        if body_size > DEFAULT_MAX_PAYLOAD_BYTES:
            raise RuntimeError(f"LLM_CONTEXT_TOO_LARGE: payload bytes {body_size} exceed {DEFAULT_MAX_PAYLOAD_BYTES}")

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if path == "/chat/completions":
            self._validate_chat_payload(payload)
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(f"{self.base_url}{path}", data=body, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = f"status={exc.code}; body={self._redacted_error_body(exc)}"
            if exc.code in {401, 403}:
                raise RuntimeError(f"BLOCKED_LLM_AUTH_FAILED: {details}") from exc
            if exc.code in {400, 404, 422}:
                raise RuntimeError(f"LLM_PROVIDER_BAD_REQUEST: {details}") from exc
            raise RuntimeError(f"BLOCKED_LLM_PROVIDER_PROTOCOL_ERROR: {details}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError("MODEL_TIMEOUT") from exc
        except urllib.error.URLError as exc:
            if isinstance(getattr(exc, "reason", None), socket.timeout):
                raise RuntimeError("MODEL_TIMEOUT") from exc
            raise RuntimeError(f"BLOCKED_LLM_PROVIDER_UNREACHABLE: {getattr(exc, 'reason', '')}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("LLM_PROVIDER_RESPONSE_INVALID: response was not valid JSON") from exc

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.0) -> dict[str, Any]:
        return self._post("/chat/completions", {"model": self.model, "messages": messages, "temperature": temperature})

    def health(self) -> dict[str, Any]:
        try:
            payload = self.chat([{"role": "user", "content": "Reply with SAFY_OK only."}], temperature=0.0)
        except RuntimeError as exc:
            return {"success": False, "status": str(exc)}
        content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"success": True, "status": "PASS_LLM_PROVIDER_HEALTHCHECK", "model": self.model, "sample": content[:64]}
