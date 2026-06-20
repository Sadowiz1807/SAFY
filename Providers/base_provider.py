from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderRequest:
    prompt: str
    intent: str
    domain: str
    target: str = "sandbox"
    redaction_profile: str = "agent_runtime-default"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResponse:
    provider_id: str
    output: dict[str, Any]
    raw_secret_detected: bool = False


class BaseProvider(Protocol):
    provider_id: str

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        ...
