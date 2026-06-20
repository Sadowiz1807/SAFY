from __future__ import annotations

from typing import Any
from Logging.redact import redact_text, redact_obj

class DriverError(Exception):
    def __init__(self, error_code: str, message: str, details: dict[str, Any] | None = None):
        self.error_code = error_code
        self.details = redact_obj(details or {})
        super().__init__(redact_text(message) or "Database driver error.")

    def to_envelope(self, driver: str | None = None, database_profile_id: str | None = None) -> dict[str, Any]:
        return {"success": False, "driver": driver, "database_profile_id": database_profile_id, "error_code": self.error_code, "message": str(self), "details": self.details}
