from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Union

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from shared.utils.helpers import get_output_dir

router = APIRouter()
logger = logging.getLogger(__name__)


class EditRequestBody(BaseModel):
    job_id: str
    query: str


@router.post("")
async def submit_edit(req: EditRequestBody) -> Dict[str, Any]:
    from backend.app import get_pipeline_service, get_state_manager
    from agents.edit_agent.agent import EditAgent
    from shared.schemas.pipeline_schema import EditResult

    svc = get_pipeline_service()
    sm = get_state_manager()

    ps = await sm.get_latest(req.job_id)
    if ps is None:
        ps = svc.get_job_state(req.job_id)
    if ps is None:
        raise HTTPException(status_code=404, detail=f"Job {req.job_id} not found")

    agent = EditAgent(state_manager=sm)
    try:
        # Run in a thread so _execute_edit_node can safely create its own
        # event loop via asyncio.new_event_loop().run_until_complete().
        # Calling that from within the already-running uvicorn loop raises
        # "Cannot run the event loop while another loop is running".
        result = await asyncio.to_thread(agent.run, req.query, ps)
    except Exception as e:
        logger.exception("Edit agent raised an unhandled exception")
        raise HTTPException(status_code=500, detail=f"Edit agent failed: {e}")

    if isinstance(result, str):
        return {"job_id": req.job_id, "clarification": result, "success": False}

    return result.model_dump()


@router.get("/{job_id}/history")
async def get_history(job_id: str) -> List[Dict[str, Any]]:
    from backend.app import get_state_manager
    sm = get_state_manager()
    records = await sm.history(job_id)
    output_dir = get_output_dir()
    for rec in records:
        vpath = os.path.join(output_dir, job_id, f"final_output_v{rec['version']}.mp4")
        has_video = os.path.exists(vpath)
        rec["has_video"] = has_video
        rec["video_url"] = f"/api/pipeline/{job_id}/video?version={rec['version']}" if has_video else None
    return records


@router.post("/{job_id}/revert/{version}")
async def revert_version(job_id: str, version: int) -> Dict[str, Any]:
    from backend.app import get_state_manager, get_pipeline_service
    sm = get_state_manager()

    try:
        ps = await sm.revert(job_id, version)
        # Update in-memory state
        svc = get_pipeline_service()
        svc.job_queue.set_state(job_id, ps)
        return {
            "job_id": job_id,
            "version": version,
            "has_video": ps.final_video_path is not None,
            "phases": {k: v.model_dump() for k, v in ps.phases.items()},
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
