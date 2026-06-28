from __future__ import annotations

from Tools.tool_result import ToolResult


class InspectWorkspaceTool:
    name = "sandbox.inspect_workspace"
    toolset = "sandbox"

    def run(self, workspace_id: str, owner_chat_id: str | None = None, expected_chat_id: str | None = None) -> ToolResult:
        if expected_chat_id and owner_chat_id and expected_chat_id != owner_chat_id:
            return ToolResult(False, {}, "TOOL_BLOCKED", ["workspace_ownership_mismatch"])
        return ToolResult(True, {"workspace_id": workspace_id, "owned": True})
