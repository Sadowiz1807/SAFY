from __future__ import annotations

from typing import Protocol, Any


class LLMAdapter(Protocol):
    def health(self) -> dict[str, Any]: ...
    def chat(self, messages: list[dict[str, str]], temperature: float = 0.0) -> dict[str, Any]: ...
