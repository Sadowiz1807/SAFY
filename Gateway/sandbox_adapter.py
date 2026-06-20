from __future__ import annotations

from dataclasses import dataclass
import os
import uuid


@dataclass(frozen=True)
class ExecutionResult:
    execution_id: str
    status: str
    rows: list[dict]
    rows_affected: int
    note: str
    no_real_execution: bool = True


class SandboxAdapter:
    """Compatibility test adapter.

    Runtime query execution should use SandboxManager.execute_readonly or a real
    connected database adapter. This adapter is disabled by default so SAFY does
    not return successful-looking fixture results in production-capable paths.
    """

    mode = "DISABLED"

    def execute(self, plan: dict, context: dict | None = None) -> ExecutionResult:
        if os.getenv("SAFY_ALLOW_TEST_SANDBOX_ADAPTER", "0") != "1":
            raise RuntimeError("SANDBOX_TEST_ADAPTER_DISABLED")
        return ExecutionResult(
            execution_id=f"exec_test_fixture_{uuid.uuid4().hex}",
            status="test_fixture_success",
            rows=[{"test_fixture": True, "statement_type": plan.get("statement_type"), "decision": plan.get("decision")}],
            rows_affected=0,
            note="Explicit test fixture adapter did not execute SQL.",
            no_real_execution=True,
        )
