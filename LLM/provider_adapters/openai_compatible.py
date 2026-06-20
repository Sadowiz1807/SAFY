from __future__ import annotations

from typing import Any
import json
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path


class OpenAICompatibleAdapter:
    def __init__(self, profile: dict[str, Any], timeout: int = 30):
        self.profile = profile
        self.timeout = timeout
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

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(f"{self.base_url}{path}", data=body, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise RuntimeError("BLOCKED_LLM_AUTH_FAILED") from exc
            if exc.code in {400, 404, 422}:
                raise RuntimeError("BLOCKED_LLM_MODEL_NOT_FOUND") from exc
            raise RuntimeError("BLOCKED_LLM_PROVIDER_PROTOCOL_ERROR") from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            raise RuntimeError("BLOCKED_LLM_PROVIDER_UNREACHABLE") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("BLOCKED_LLM_PROVIDER_PROTOCOL_ERROR") from exc

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.0) -> dict[str, Any]:
        return self._post("/chat/completions", {"model": self.model, "messages": messages, "temperature": temperature})

    def health(self) -> dict[str, Any]:
        try:
            payload = self.chat([{"role": "user", "content": "Reply with SAFY_OK only."}], temperature=0.0)
        except RuntimeError as exc:
            return {"success": False, "status": str(exc)}
        content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"success": True, "status": "PASS_LLM_PROVIDER_HEALTHCHECK", "model": self.model, "sample": content[:64]}
