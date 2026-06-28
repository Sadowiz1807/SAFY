from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

from Tools.tool_result import ToolResult


class CleanupWorkspaceTool:
    name = "sandbox.cleanup_workspace"
    toolset = "sandbox"

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = Path(base_dir or Path(tempfile.gettempdir()) / "safy_agent_runtime_sandbox")

    def run(self, workspace_id: str) -> ToolResult:
        removed = 0
        for manifest in self.base_dir.glob(f"**/{workspace_id}/workspace.json"):
            workspace_dir = manifest.parent
            try:
                shutil.rmtree(workspace_dir)
                removed += 1
            except FileNotFoundError:
                pass
            except Exception as exc:
                return ToolResult(False, {"workspace_id": workspace_id}, "SANDBOX_CLEANUP_FAILED", [type(exc).__name__])
        return ToolResult(True, {"workspace_id": workspace_id, "cleanup": "completed", "removed": removed})
