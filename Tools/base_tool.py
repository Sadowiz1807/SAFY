from __future__ import annotations

from typing import Protocol
from .tool_result import ToolResult


class BaseTool(Protocol):
    name: str
    toolset: str

    def run(self, **kwargs) -> ToolResult:
        ...
