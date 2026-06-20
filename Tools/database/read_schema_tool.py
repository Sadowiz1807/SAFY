from __future__ import annotations

from pathlib import Path
from Sandbox.sqlite_runner import SQLiteSandboxRunner
from Sandbox.sandbox_manager import SandboxManager
from Tools.tool_result import ToolResult


class ReadSchemaTool:
    name = "database.read_schema"
    toolset = "database"

    def __init__(self, runner: SQLiteSandboxRunner | None = None, manager: SandboxManager | None = None) -> None:
        self.runner = runner or SQLiteSandboxRunner()
        self.manager = manager or SandboxManager()

    def run(self, db_path: Path, target: str = "sandbox") -> ToolResult:
        if target != "sandbox":
            return ToolResult(False, {}, "TOOL_BLOCKED", ["connected_schema_read_deferred_api_runtime"])
        try:
            self.manager.manifest_for_path(Path(db_path))
            return ToolResult(True, {"schema": self.runner.read_schema(Path(db_path))})
        except ValueError:
            return ToolResult(False, {}, "SANDBOX_WORKSPACE_FAILED", ["db_path_outside_managed_sandbox"])
        except Exception:
            return ToolResult(False, {}, "SANDBOX_SCHEMA_READBACK_FAILED")
