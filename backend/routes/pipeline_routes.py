from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter()


class StartPipelineRequest(BaseModel):
    prompt: str
    style: str = "cinematic"
    add_subtitles: bool = False


@router.post("/start")
async def start_pipeline(req: StartPipelineRequest, pipeline_service=None) -> Dict[str, Any]:
    from backend.app import get_pipeline_service
    svc = pipeline_service or get_pipeline_service()
    job_id = await svc.create_job(req.prompt, req.style, req.add_subtitles)
    return {"job_id": job_id, "status": "queued"}


@router.get("/{job_id}/status")
async def get_status(job_id: str) -> Dict[str, Any]:
    from backend.app import get_pipeline_service
    svc = get_pipeline_service()
    state = svc.get_job_state(job_id)
    queue_status = svc.get_job_status(job_id)

    if state is None:
        return {"job_id": job_id, "status": queue_status, "phases": {}}

    return {
        "job_id": job_id,
        "status": queue_status,
        "phases": {k: v.model_dump() for k, v in state.phases.items()},
        "has_video": state.final_video_path is not None,
        "version": state.version,
    }


@router.get("/{job_id}/video")
async def get_video(job_id: str, version: Optional[int] = None):
    from backend.app import get_pipeline_service, get_state_manager
    svc = get_pipeline_service()

    if version is not None:
        sm = get_state_manager()
        try:
            ps = await sm.revert(job_id, version)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Version {version} not found")
        video_path = ps.final_video_path
    else:
        state = svc.get_job_state(job_id)
        if not state or not state.final_video_path:
            raise HTTPException(status_code=404, detail="Video not ready yet")
        video_path = state.final_video_path

    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"animora_{job_id}.mp4",
    )


@router.post("/{job_id}/subtitles")
async def add_subtitles(job_id: str) -> Dict[str, Any]:
    from backend.app import get_pipeline_service
    from mcp.tool_executor import ToolExecutor
    from mcp.tool_registry import ToolRegistry
    import os

    svc = get_pipeline_service()
    ps = svc.get_job_state(job_id)
    if not ps or not ps.final_video_path:
        raise HTTPException(status_code=404, detail="Video not ready for this job")
    if not os.path.exists(ps.final_video_path):
        raise HTTPException(status_code=404, detail="Video file not found on disk")
    if not ps.story or not ps.timing_manifest:
        raise HTTPException(status_code=400, detail="Story/timing data missing — cannot generate subtitles")

    scene_payloads = [
        {"id": s.id, "dialogue": [d.model_dump() for d in s.dialogue]}
        for s in ps.story.scenes
    ]

    sub_path = ps.final_video_path.replace(".mp4", "_subtitled.mp4")
    ToolRegistry.auto_register_all()
    executor = ToolExecutor(ToolRegistry)
    result = executor.run(
        "subtitle",
        {
            "video_path": ps.final_video_path,
            "scenes": scene_payloads,
            "output_path": sub_path,
            "scene_timings": ps.timing_manifest.scene_timings,
        },
    )
    if not result.success:
        raise HTTPException(status_code=500, detail=f"Subtitle generation failed: {result.error}")

    ps.final_video_path = sub_path
    svc.job_queue.set_state(job_id, ps)
    return {"job_id": job_id, "video_path": sub_path, "status": "subtitles_added"}


@router.post("/{job_id}/rerun/{phase}")
async def rerun_phase(job_id: str, phase: str, add_subtitles: bool = False) -> Dict[str, Any]:
    from backend.app import get_pipeline_service, get_workflow
    if phase not in ("story", "audio", "video"):
        raise HTTPException(status_code=400, detail=f"Invalid phase: {phase}")

    svc = get_pipeline_service()
    workflow = get_workflow()
    ps = await svc.rerun_phase(job_id, phase, workflow, add_subtitles=add_subtitles)
    return {"job_id": job_id, "phase": phase, "status": "completed" if ps else "failed"}
