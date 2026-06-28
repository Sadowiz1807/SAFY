from __future__ import annotations

import re
from Tools.tool_result import ToolResult


class SanitizeIdentifierTool:
    name = "sql.sanitize_identifier"
    toolset = "sql"

    def run(self, identifier: str) -> ToolResult:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", identifier or ""):
            return ToolResult(False, {}, "SQL_PARSE_ERROR", ["invalid_identifier"])
        return ToolResult(True, {"identifier": identifier})
