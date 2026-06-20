from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
import random


@dataclass
class ConfirmationRecord:
    check_id: str
    sql_hash: str
    target: str
    code: str
    expires_at: datetime
    attempt_count: int = 0
    consumed_at: datetime | None = None


class HighRiskCodeState:
    def __init__(self, ttl_seconds: int = 300, code_generator: Callable[[], str] | None = None, clock: Callable[[], datetime] | None = None):
        self.ttl_seconds = ttl_seconds
        self._code_generator = code_generator or (lambda: f"{random.SystemRandom().randint(0, 9999):04d}")
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._records: dict[str, ConfirmationRecord] = {}

    def generate(self, check_id: str, sql_hash: str, target: str) -> ConfirmationRecord:
        code = str(self._code_generator())
        if not (len(code) == 4 and code.isdigit()):
            raise ValueError("Confirmation code generator must return a 4-digit string.")
        record = ConfirmationRecord(check_id, sql_hash, target, code, self._clock() + timedelta(seconds=self.ttl_seconds))
        self._records[check_id] = record
        return record

    def consume(self, check_id: str) -> bool:
        record = self._records.get(check_id)
        if not record or record.consumed_at is not None:
            return False
        record.consumed_at = self._clock()
        return True

    def validate(self, check_id: str, sql_hash: str, target: str, code: str) -> tuple[bool, str]:
        record = self._records.get(check_id)
        now = self._clock()
        if not record:
            return False, "CONFIRMATION_CODE_MISSING"
        if record.consumed_at is not None:
            return False, "CONFIRMATION_CODE_CONSUMED"
        if now > record.expires_at:
            return False, "CONFIRMATION_CODE_EXPIRED"
        if record.sql_hash != sql_hash:
            return False, "QUERY_SQL_CHANGED"
        if record.target != target:
            return False, "QUERY_TARGET_MISMATCH"
        if record.code != code:
            record.attempt_count += 1
            return False, "CONFIRMATION_CODE_INVALID"
        record.attempt_count += 1
        record.consumed_at = now
        return True, "CONFIRMATION_CODE_VALID"
