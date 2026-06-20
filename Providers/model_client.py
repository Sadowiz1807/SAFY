from __future__ import annotations

from Logging.redact import redact_obj
from .base_provider import ProviderRequest, ProviderResponse
from .provider_registry import ProviderRegistry


class ModelClient:
    def __init__(self, registry: ProviderRegistry | None = None) -> None:
        self.registry = registry or ProviderRegistry()

    def generate(self, request: ProviderRequest, provider_id: str | None = None) -> ProviderResponse:
        safe_request = ProviderRequest(
            prompt=str(redact_obj(request.prompt)),
            intent=request.intent,
            domain=request.domain,
            target=request.target,
            redaction_profile=request.redaction_profile,
            metadata=redact_obj(request.metadata),
        )
        provider = self.registry.get(provider_id)
        response = provider.generate(safe_request)
        if not isinstance(response.output, dict):
            raise ValueError("PROVIDER_OUTPUT_INVALID")
        return response
