from __future__ import annotations

from pathlib import Path
import json
import os
import secrets
import string

class LocalSecretStore:
    def __init__(self, root: Path):
        self.path = root / "secrets" / "sandbox_secrets.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def _read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def _write(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def create_password(self, sandbox_id: str, purpose: str = "readonly_credential") -> str:
        alphabet = string.ascii_letters + string.digits + "_!"
        password = "safy_sb_" + "".join(secrets.choice(alphabet) for _ in range(24))
        safe_purpose = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in purpose)
        ref = f"secret://sandbox/{sandbox_id}/{safe_purpose}"
        data = self._read()
        data[ref] = password
        self._write(data)
        return ref

    def get(self, ref: str) -> str | None:
        return self._read().get(ref)

    def delete(self, ref: str | None) -> None:
        if not ref:
            return
        data = self._read()
        data.pop(ref, None)
        self._write(data)
