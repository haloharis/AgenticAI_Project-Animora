from __future__ import annotations

import asyncio
from typing import Any, Dict

from mcp.base_tool import BaseTool, ToolOutput


class StateTool(BaseTool):
    name = "state_tool"
    description = "State management operations: snapshot, revert, get_history"

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        operation: str = inputs["operation"]

        try:
            from state_manager.state_manager import StateManager
            sm = StateManager.get_instance()
        except Exception as e:
            return ToolOutput(success=False, error=f"StateManager not available: {e}")

        loop = asyncio.new_event_loop()
        try:
            if operation == "history":
                job_id = inputs["job_id"]
                result = loop.run_until_complete(sm.history(job_id))
                return ToolOutput(success=True, data=result)

            elif operation == "get_latest":
                job_id = inputs["job_id"]
                state = loop.run_until_complete(sm.get_latest(job_id))
                return ToolOutput(success=True, data=state.model_dump() if state else None)

            return ToolOutput(success=False, error=f"Unknown operation: {operation}")
        finally:
            loop.close()
