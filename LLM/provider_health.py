from __future__ import annotations

from .provider_adapters.openai_compatible import OpenAICompatibleAdapter


def adapter_for(profile: dict):
    return OpenAICompatibleAdapter(profile)


def test_profile(profile: dict) -> dict:
    return adapter_for(profile).health()


test_profile.__test__ = False
