from __future__ import annotations

import uuid
from typing import Any, Optional

from backend.services.job_queue import JobQueue
from shared.schemas.pipeline_schema import PipelineState


class PipelineService:
    def __init__(self, job_queue: JobQueue) -> None:
        self.job_queue = job_queue

    async def create_job(self, prompt: str, style: str = "cinematic", add_subtitles: bool = False) -> str:
        job_id = str(uuid.uuid4())
        await self.job_queue.enqueue(job_id, prompt, style, add_subtitles)
        return job_id

    def get_job_state(self, job_id: str) -> Optional[PipelineState]:
        state = self.job_queue.get_state(job_id)
        if state and isinstance(state, dict):
            return PipelineState(**state)
        return state

    def get_job_status(self, job_id: str) -> str:
        return self.job_queue.get_status(job_id)

    async def rerun_phase(self, job_id: str, phase: str, workflow, add_subtitles: bool = False) -> Optional[PipelineState]:
        return await workflow.rerun_phase(job_id, phase, add_subtitles=add_subtitles)
