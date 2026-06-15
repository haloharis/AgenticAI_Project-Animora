from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

from agents.orchestrator.state import update_phase_status
from shared.schemas.pipeline_schema import PhaseStatus, PipelineState
from state_manager.state_manager import StateManager

logger = logging.getLogger(__name__)


class PipelineWorkflow:
    def __init__(self, sse_manager=None, state_manager: Optional[StateManager] = None) -> None:
        self.sse_manager = sse_manager
        self.state_manager = state_manager or StateManager.get_instance()

    async def _emit(self, job_id: str, event: dict) -> None:
        if self.sse_manager:
            await self.sse_manager.emit(job_id, event)

    def _make_log_fn(self, job_id: str, phase: str, loop: asyncio.AbstractEventLoop) -> Callable:
        """Returns a sync callable that logs to Python logger and emits a 'log' SSE event."""
        def log_fn(message: str, level: str = "info") -> None:
            getattr(logger, level if level in ("info", "warning", "error") else "info")(message)
            if self.sse_manager:
                asyncio.run_coroutine_threadsafe(
                    self.sse_manager.emit(job_id, {"type": "log", "phase": phase, "level": level, "message": message}),
                    loop,
                )
        return log_fn

    def _make_progress_fn(self, job_id: str, phase: str, loop: asyncio.AbstractEventLoop) -> Callable:
        """Returns a sync callable that emits a progress SSE event for a running phase."""
        def progress_fn(pct: int) -> None:
            if self.sse_manager:
                asyncio.run_coroutine_threadsafe(
                    self.sse_manager.emit(job_id, {"phase": phase, "status": "running", "progress": int(pct)}),
                    loop,
                )
        return progress_fn

    async def run_pipeline(
        self, job_id: str, user_prompt: str, style: str = "cinematic", add_subtitles: bool = False
    ) -> PipelineState:
        from mcp.tool_registry import ToolRegistry
        ToolRegistry.auto_register_all()

        loop = asyncio.get_event_loop()
        ps = PipelineState(job_id=job_id, user_prompt=user_prompt, style=style)
        await self.state_manager.initialize()
        ps = await self.state_manager.snapshot(ps, phase="init", note="Pipeline started")

        # --- Phase 1: Story ---
        await self._emit(job_id, {"phase": "story", "status": "running", "progress": 0})
        await self._emit(job_id, {"type": "log", "phase": "story", "level": "info", "message": "Starting story generation…"})
        ps = update_phase_status(ps, "story", PhaseStatus.running)
        try:
            from agents.story_agent.agent import StoryAgent
            log_fn = self._make_log_fn(job_id, "story", loop)
            progress_fn = self._make_progress_fn(job_id, "story", loop)
            story = await loop.run_in_executor(
                None, lambda: StoryAgent().run(user_prompt, style, log_fn=log_fn, progress_fn=progress_fn)
            )
            ps.story = story
            ps = update_phase_status(ps, "story", PhaseStatus.completed, progress_pct=100)
            ps = await self.state_manager.snapshot(ps, phase="story", note="Story generated")
            await self._emit(job_id, {"type": "log", "phase": "story", "level": "info", "message": "Story generation complete."})
            await self._emit(job_id, {"phase": "story", "status": "completed", "progress": 100})
        except Exception as e:
            logger.exception(f"Story phase failed: {e}")
            await self._emit(job_id, {"type": "log", "phase": "story", "level": "error", "message": f"Story failed: {e}"})
            ps = update_phase_status(ps, "story", PhaseStatus.failed, error=str(e))
            await self._emit(job_id, {"phase": "story", "status": "failed", "error": str(e)})
            await self._emit(job_id, {"type": "done", "success": False})
            return ps

        # --- Phase 2: Audio ---
        await self._emit(job_id, {"phase": "audio", "status": "running", "progress": 0})
        await self._emit(job_id, {"type": "log", "phase": "audio", "level": "info", "message": "Starting audio synthesis…"})
        ps = update_phase_status(ps, "audio", PhaseStatus.running)
        try:
            from agents.audio_agent.agent import AudioAgent
            log_fn = self._make_log_fn(job_id, "audio", loop)
            progress_fn = self._make_progress_fn(job_id, "audio", loop)
            manifest = await loop.run_in_executor(
                None, lambda: AudioAgent().run(ps.story, job_id, log_fn=log_fn, progress_fn=progress_fn)
            )
            ps.timing_manifest = manifest
            ps = update_phase_status(ps, "audio", PhaseStatus.completed, progress_pct=100)
            ps = await self.state_manager.snapshot(ps, phase="audio", note="Audio generated")
            await self._emit(job_id, {"type": "log", "phase": "audio", "level": "info", "message": "Audio synthesis complete."})
            await self._emit(job_id, {"phase": "audio", "status": "completed", "progress": 100})
        except Exception as e:
            logger.exception(f"Audio phase failed: {e}")
            await self._emit(job_id, {"type": "log", "phase": "audio", "level": "error", "message": f"Audio failed: {e}"})
            ps = update_phase_status(ps, "audio", PhaseStatus.failed, error=str(e))
            await self._emit(job_id, {"phase": "audio", "status": "failed", "error": str(e)})
            await self._emit(job_id, {"type": "done", "success": False})
            return ps

        # --- Phase 3: Video ---
        await self._emit(job_id, {"phase": "video", "status": "running", "progress": 0})
        await self._emit(job_id, {"type": "log", "phase": "video", "level": "info", "message": "Starting video composition…"})
        ps = update_phase_status(ps, "video", PhaseStatus.running)
        try:
            from agents.video_agent.agent import VideoAgent
            log_fn = self._make_log_fn(job_id, "video", loop)
            progress_fn = self._make_progress_fn(job_id, "video", loop)
            video_path = await loop.run_in_executor(
                None, lambda: VideoAgent().run(ps.story, ps.timing_manifest, job_id, add_subtitles=add_subtitles, log_fn=log_fn, progress_fn=progress_fn)
            )
            ps.final_video_path = video_path
            ps = update_phase_status(ps, "video", PhaseStatus.completed, progress_pct=100)
            ps = await self.state_manager.snapshot(ps, phase="video", note="Video generated")
            await self._emit(job_id, {"type": "log", "phase": "video", "level": "info", "message": "Video composition complete."})
            await self._emit(job_id, {"phase": "video", "status": "completed", "progress": 100})
        except Exception as e:
            logger.exception(f"Video phase failed: {e}")
            await self._emit(job_id, {"type": "log", "phase": "video", "level": "error", "message": f"Video failed: {e}"})
            ps = update_phase_status(ps, "video", PhaseStatus.failed, error=str(e))
            await self._emit(job_id, {"phase": "video", "status": "failed", "error": str(e)})

        await self._emit(job_id, {"type": "done", "success": ps.final_video_path is not None})
        return ps

    async def rerun_phase(self, job_id: str, phase: str, add_subtitles: bool = False) -> PipelineState:
        ps = await self.state_manager.get_latest(job_id)
        if not ps:
            raise ValueError(f"No pipeline state found for job {job_id}")

        from mcp.tool_registry import ToolRegistry
        ToolRegistry.auto_register_all()

        loop = asyncio.get_event_loop()
        log_fn = self._make_log_fn(job_id, phase, loop)
        progress_fn = self._make_progress_fn(job_id, phase, loop)

        await self._emit(job_id, {"phase": phase, "status": "running", "progress": 0})
        await self._emit(job_id, {"type": "log", "phase": phase, "level": "info", "message": f"Re-running {phase} phase…"})
        ps = update_phase_status(ps, phase, PhaseStatus.running)

        try:
            if phase == "story":
                from agents.story_agent.agent import StoryAgent
                story = await loop.run_in_executor(
                    None, lambda: StoryAgent().run(ps.user_prompt, ps.style, log_fn=log_fn, progress_fn=progress_fn)
                )
                ps.story = story
                ps = update_phase_status(ps, phase, PhaseStatus.completed, progress_pct=100)
            elif phase == "audio":
                from agents.audio_agent.agent import AudioAgent
                manifest = await loop.run_in_executor(
                    None, lambda: AudioAgent().run(ps.story, job_id, log_fn=log_fn, progress_fn=progress_fn)
                )
                ps.timing_manifest = manifest
                ps = update_phase_status(ps, phase, PhaseStatus.completed, progress_pct=100)
            elif phase == "video":
                from agents.video_agent.agent import VideoAgent
                video_path = await loop.run_in_executor(
                    None, lambda: VideoAgent().run(ps.story, ps.timing_manifest, job_id, add_subtitles=add_subtitles, log_fn=log_fn, progress_fn=progress_fn)
                )
                ps.final_video_path = video_path
                ps = update_phase_status(ps, phase, PhaseStatus.completed, progress_pct=100)

            ps = await self.state_manager.snapshot(ps, phase=phase, note=f"Re-run: {phase}")
            await self._emit(job_id, {"phase": phase, "status": "completed", "progress": 100})
            await self._emit(job_id, {"type": "done", "success": True})
        except Exception as e:
            logger.exception(f"Rerun of phase '{phase}' failed: {e}")
            await self._emit(job_id, {"type": "log", "phase": phase, "level": "error", "message": f"Re-run failed: {e}"})
            ps = update_phase_status(ps, phase, PhaseStatus.failed, error=str(e))
            await self._emit(job_id, {"phase": phase, "status": "failed", "error": str(e)})

        return ps
