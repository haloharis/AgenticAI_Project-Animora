from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator, Dict, List, Optional

logger = logging.getLogger(__name__)


class SSEManager:
    _instance: Optional["SSEManager"] = None

    def __init__(self) -> None:
        self._queues:  Dict[str, asyncio.Queue] = {}
        self._history: Dict[str, List[dict]]    = {}

    @classmethod
    def get_instance(cls) -> "SSEManager":
        if cls._instance is None:
            cls._instance = SSEManager()
        return cls._instance

    def connect(self, job_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        # Replay any events emitted before the client connected (fixes race condition)
        for evt in self._history.get(job_id, []):
            q.put_nowait(evt)
        self._queues[job_id] = q
        return q

    def disconnect(self, job_id: str) -> None:
        self._queues.pop(job_id, None)

    async def emit(self, job_id: str, event: dict) -> None:
        self._history.setdefault(job_id, []).append(event)
        q = self._queues.get(job_id)
        if q:
            await q.put(event)

    async def stream(self, job_id: str) -> AsyncGenerator[dict, None]:
        q = self.connect(job_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Keepalive is inside the loop so it continues rather than ending the generator
                    yield {"type": "keepalive"}
                    continue
                yield event
                if event.get("type") == "done":
                    break
        except asyncio.CancelledError:
            pass
        finally:
            self.disconnect(job_id)
