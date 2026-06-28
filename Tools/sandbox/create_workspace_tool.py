from __future__ import annotations

from Sandbox.sandbox_manager import SandboxManager
from Tools.tool_result import ToolResult


class CreateWorkspaceTool:
    name = "sandbox.create_workspace"
    toolset = "sandbox"

    def __init__(self, manager: SandboxManager | None = None) -> None:
        self.manager = manager or SandboxManager()

    def run(self, chat_id: str, workflow_id: str, target: str = "sandbox") -> ToolResult:
        if target != "sandbox":
            return ToolResult(False, {}, "SANDBOX_WORKSPACE_FAILED", ["target_not_sandbox"])
        return ToolResult(True, self.manager.create_workspace(chat_id, workflow_id))
