from __future__ import annotations

import os
from typing import Any, Dict

from mcp.base_tool import BaseTool, ToolOutput
from shared.utils.helpers import load_json, save_json


class FileTool(BaseTool):
    name = "file_tool"
    description = "File system operations: read, write, delete, list, exists"

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        operation: str = inputs["operation"]
        path: str = inputs.get("path", "")

        if operation == "read":
            data = load_json(path)
            return ToolOutput(success=True, data=data)

        elif operation == "write":
            content = inputs["content"]
            save_json(content, path)
            return ToolOutput(success=True, data={"path": path})

        elif operation == "delete":
            if os.path.exists(path):
                os.remove(path)
            return ToolOutput(success=True, data={"deleted": path})

        elif operation == "list":
            if not os.path.isdir(path):
                return ToolOutput(success=False, error=f"Not a directory: {path}")
            files = os.listdir(path)
            return ToolOutput(success=True, data={"files": files})

        elif operation == "exists":
            return ToolOutput(success=True, data={"exists": os.path.exists(path)})

        return ToolOutput(success=False, error=f"Unknown operation: {operation}")
