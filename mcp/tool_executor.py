from __future__ import annotations

import logging
from typing import Any, Dict, List

from mcp.base_tool import ToolOutput
from mcp.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutor:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or ToolRegistry

    def run(self, tool_name: str, inputs: Dict[str, Any]) -> ToolOutput:
        tool = self.registry.get(tool_name)
        logger.debug(f"Running tool '{tool_name}' with inputs: {list(inputs.keys())}")
        return tool.safe_execute(inputs)

    def run_batch(self, calls: List[Dict[str, Any]]) -> List[ToolOutput]:
        results = []
        for call in calls:
            tool_name = call["tool"]
            inputs = call.get("inputs", {})
            results.append(self.run(tool_name, inputs))
        return results
