from __future__ import annotations

from typing import Any

from .demo_provider import DemoProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, Any] = {"test": DemoProvider(), "demo": DemoProvider()}

    def register(self, provider_id: str, provider: Any) -> None:
        if not provider_id or not hasattr(provider, "generate"):
            raise ValueError("invalid_provider")
        self._providers[provider_id] = provider

    def get(self, provider_id: str | None = None) -> Any:
        pid = provider_id or "test"
        if pid != "test" and pid not in self._providers:
            raise ValueError("PROVIDER_UNAVAILABLE")
        return self._providers.get(pid, self._providers["test"])
