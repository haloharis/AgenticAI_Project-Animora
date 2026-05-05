from __future__ import annotations

import json

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

router = APIRouter()


@router.get("/{job_id}")
async def sse_stream(job_id: str):
    from backend.app import get_sse_manager
    sse_manager = get_sse_manager()

    async def event_generator():
        async for event in sse_manager.stream(job_id):
            yield {"data": json.dumps(event)}

    return EventSourceResponse(event_generator())
