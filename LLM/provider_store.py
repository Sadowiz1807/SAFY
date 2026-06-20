from __future__ import annotations

from pathlib import Path
from typing import Any

from DataStore.config_loader import load_json, write_json_atomic
from .provider_profiles import ModelProfileError, ModelProviderProfile, redact_profile


class ModelProviderStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            write_json_atomic(self.path, {"schema_version": 1, "profiles": []})

    def _read(self) -> dict[str, Any]:
        return load_json(self.path)

    def list(self, redacted: bool = True) -> list[dict[str, Any]]:
        profiles = [ModelProviderProfile.from_dict(p).to_dict() for p in self._read().get("profiles", [])]
        return [redact_profile(p) for p in profiles] if redacted else profiles

    def get(self, profile_id: str, redacted: bool = True) -> dict[str, Any]:
        for profile in self.list(redacted=False):
            if profile["profile_id"] == profile_id:
                return redact_profile(profile) if redacted else profile
        raise ModelProfileError("PROFILE_NOT_FOUND", f"Model profile not found: {profile_id}")

    def active(self, redacted: bool = True) -> dict[str, Any]:
        for profile in self.list(redacted=False):
            if profile.get("is_active"):
                return redact_profile(profile) if redacted else profile
        raise ModelProfileError("PROFILE_NOT_FOUND", "No active model profile configured.")

    def save(self, profile: dict[str, Any], overwrite: bool = False) -> dict[str, Any]:
        normalized = ModelProviderProfile.from_dict(profile, for_write=True).to_dict()
        data = self._read()
        profiles = [ModelProviderProfile.from_dict(p).to_dict() for p in data.get("profiles", [])]
        existing = [i for i, p in enumerate(profiles) if p["profile_id"] == normalized["profile_id"]]
        if existing and not overwrite:
            raise ModelProfileError("DUPLICATE_PROFILE_ID", f"Duplicate profile_id: {normalized['profile_id']}")
        if normalized.get("is_active"):
            profiles = [{**p, "is_active": False} for p in profiles]
        if existing:
            normalized["created_at"] = profiles[existing[0]].get("created_at") or normalized["created_at"]
            profiles[existing[0]] = normalized
        else:
            profiles.append(normalized)
        write_json_atomic(self.path, {"schema_version": 1, "profiles": sorted(profiles, key=lambda p: p["profile_id"])})
        return redact_profile(normalized)

    def patch(self, profile_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        current = self.get(profile_id, redacted=False)
        return self.save({**current, **updates, "profile_id": profile_id}, overwrite=True)

    def activate(self, profile_id: str) -> dict[str, Any]:
        target = self.get(profile_id, redacted=False)
        target["is_active"] = True
        return self.save(target, overwrite=True)

    def delete(self, profile_id: str) -> dict[str, Any]:
        profiles = self.list(redacted=False)
        remaining = [p for p in profiles if p["profile_id"] != profile_id]
        if len(remaining) == len(profiles):
            raise ModelProfileError("PROFILE_NOT_FOUND", f"Model profile not found: {profile_id}")
        write_json_atomic(self.path, {"schema_version": 1, "profiles": remaining})
        return {"deleted": True, "profile_id": profile_id}
