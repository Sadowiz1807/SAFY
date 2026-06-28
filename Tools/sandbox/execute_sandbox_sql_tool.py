from __future__ import annotations

from pathlib import Path
from Sandbox.sqlite_runner import SQLiteSandboxRunner
from Sandbox.sandbox_manager import SandboxManager
from Tools.tool_result import ToolResult


class ExecuteSandboxSQLTool:
    name = "sandbox.execute_sql"
    toolset = "sandbox"

    def __init__(self, runner: SQLiteSandboxRunner | None = None, manager: SandboxManager | None = None) -> None:
        self.runner = runner or SQLiteSandboxRunner()
        self.manager = manager or SandboxManager()

    def run(self, db_path: Path, statement: str, target: str = "sandbox") -> ToolResult:
        if target != "sandbox":
            return ToolResult(False, {}, "TOOL_BLOCKED", ["non_sandbox_execution_blocked"])
        try:
            self.manager.manifest_for_path(Path(db_path))
            self.runner.execute(Path(db_path), statement)
        except ValueError:
            return ToolResult(False, {}, "SANDBOX_WORKSPACE_FAILED", ["db_path_outside_managed_sandbox"])
        except Exception as exc:
            return ToolResult(False, {}, "TOOL_EXECUTION_FAILED", [type(exc).__name__])
        return ToolResult(True, {"executed": True})
