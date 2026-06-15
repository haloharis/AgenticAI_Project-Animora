from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

Job = Tuple[str, str, str, bool]  # (job_id, prompt, style, add_subtitles)


class JobQueue:
    _instance: Optional["JobQueue"] = None

    def __init__(self) -> None:
        self._queue: asyncio.Queue[Job] = asyncio.Queue()
        self._status: Dict[str, str] = {}
        self._states: Dict[str, Any] = {}
        self._worker_task: Optional[asyncio.Task] = None

    @classmethod
    def get_instance(cls) -> "JobQueue":
        if cls._instance is None:
            cls._instance = JobQueue()
        return cls._instance

    async def enqueue(self, job_id: str, prompt: str, style: str, add_subtitles: bool = False) -> None:
        self._status[job_id] = "queued"
        await self._queue.put((job_id, prompt, style, add_subtitles))
        logger.info(f"Job {job_id} enqueued")

    def get_status(self, job_id: str) -> str:
        return self._status.get(job_id, "unknown")

    def set_state(self, job_id: str, state: Any) -> None:
        self._states[job_id] = state

    def get_state(self, job_id: str) -> Any:
        return self._states.get(job_id)

    async def start_worker(self, workflow_factory) -> None:
        self._worker_task = asyncio.create_task(self._worker(workflow_factory))
        logger.info("Job queue worker started")

    async def _worker(self, workflow_factory) -> None:
        while True:
            try:
                job_id, prompt, style, add_subtitles = await self._queue.get()
                self._status[job_id] = "running"
                logger.info(f"Processing job {job_id}")
                try:
                    workflow = workflow_factory()
                    ps = await workflow.run_pipeline(job_id, prompt, style, add_subtitles=add_subtitles)
                    self.set_state(job_id, ps)
                    self._status[job_id] = "completed"
                    logger.info(f"Job {job_id} completed")
                except Exception as e:
                    logger.exception(f"Job {job_id} failed: {e}")
                    self._status[job_id] = "failed"
                finally:
                    self._queue.task_done()
            except Exception as e:
                logger.exception(f"Worker error: {e}")
                await asyncio.sleep(1)
