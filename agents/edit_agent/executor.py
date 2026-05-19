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

    def _run_story_rerun(self, inputs: Dict[str, Any], pipeline_state: PipelineState) -> None:
        """Re-generate story, audio, and video after a script edit."""
        from agents.story_agent.agent import StoryAgent
        from agents.audio_agent.agent import AudioAgent
        from agents.video_agent.agent import VideoAgent

        edit_instruction = inputs.get("edit_instruction", "")
        original_prompt = inputs.get("original_prompt", pipeline_state.user_prompt)
        style = inputs.get("style", pipeline_state.style)
        job_id = inputs.get("job_id", pipeline_state.job_id)

        modified_prompt = f"{original_prompt}\n\nEdit instruction: {edit_instruction}" if edit_instruction else original_prompt
        logger.info(f"Script re-run with prompt: {modified_prompt[:120]}…")

        story = StoryAgent().run(modified_prompt, style)
        pipeline_state.story = story
        pipeline_state.user_prompt = modified_prompt

        manifest = AudioAgent().run(story, job_id)
        pipeline_state.timing_manifest = manifest

        video_path = VideoAgent().run(story, manifest, job_id)
        pipeline_state.final_video_path = video_path

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

                if tool_name == "__story_rerun__":
                    self._run_story_rerun(inputs, pipeline_state)
                    continue

                if tool_name == "__update_final_video__":
                    pipeline_state.final_video_path = inputs["new_path"]
                    continue

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
