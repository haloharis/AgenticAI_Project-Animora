from __future__ import annotations

import logging
from typing import Any, Dict, List

from mcp.tool_executor import ToolExecutor
from mcp.tool_registry import ToolRegistry
from shared.schemas.pipeline_schema import EditAction, EditResult, PipelineState
from state_manager.state_manager import StateManager

logger = logging.getLogger(__name__)


class EditExecutor:
    def __init__(self, state_manager: StateManager | None = None) -> None:
        self.tool_executor = ToolExecutor(ToolRegistry)
        self.state_manager = state_manager or StateManager.get_instance()

    async def execute(
        self,
        plan: List[Dict[str, Any]],
        pipeline_state: PipelineState,
        action: EditAction,
    ) -> EditResult:
        prev_version = pipeline_state.version

        try:
            for call in plan:
                tool_name = call["tool"]
                inputs = call.get("inputs", {})
                result = self.tool_executor.run(tool_name, inputs)
                if not result.success and tool_name != "logger_tool":
                    logger.warning(f"Tool '{tool_name}' failed: {result.error}")

            # Snapshot new state
            pipeline_state = await self.state_manager.snapshot(
                pipeline_state,
                phase=action.intent.value,
                note=f"Edit: {action.intent.value} on {action.target}",
            )

            return EditResult(
                job_id=pipeline_state.job_id,
                action=action,
                success=True,
                message=f"Edit '{action.intent.value}' applied successfully",
                new_version=pipeline_state.version,
            )

        except Exception as e:
            logger.exception(f"Edit execution failed: {e}")
            # Attempt revert to previous version
            try:
                await self.state_manager.revert(pipeline_state.job_id, prev_version)
            except Exception:
                pass

            return EditResult(
                job_id=pipeline_state.job_id,
                action=action,
                success=False,
                message=f"Edit failed and reverted: {e}",
                new_version=prev_version,
            )
