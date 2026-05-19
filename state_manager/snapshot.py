from __future__ import annotations

import os
import shutil
from typing import Optional

from shared.schemas.pipeline_schema import PipelineState
from shared.utils.helpers import get_state_dir, get_timestamp, load_json, save_json
from state_manager.storage import SQLiteStorage


class SnapshotManager:
    def __init__(self, storage: SQLiteStorage, state_dir: Optional[str] = None) -> None:
        self.storage = storage
        self.state_dir = state_dir or get_state_dir()

    async def save(
        self,
        pipeline_state: PipelineState,
        phase: str = "",
        note: str = "",
    ) -> str:
        # Preserve this version's video as its own file so history entries
        # are not lost when subsequent edits overwrite final_output.mp4.
        if pipeline_state.final_video_path and os.path.exists(pipeline_state.final_video_path):
            video_dir = os.path.dirname(pipeline_state.final_video_path)
            versioned = os.path.join(video_dir, f"final_output_v{pipeline_state.version}.mp4")
            if os.path.abspath(pipeline_state.final_video_path) != os.path.abspath(versioned):
                shutil.copy2(pipeline_state.final_video_path, versioned)
                pipeline_state.final_video_path = versioned

        job_dir = os.path.join(self.state_dir, pipeline_state.job_id)
        os.makedirs(job_dir, exist_ok=True)

        path = os.path.join(job_dir, f"v{pipeline_state.version}.json")
        save_json(pipeline_state.model_dump(mode="json"), path)

        await self.storage.insert_version(
            job_id=pipeline_state.job_id,
            version=pipeline_state.version,
            snapshot_path=path,
            created_at=get_timestamp(),
            phase=phase,
            note=note,
        )
        return path

    async def load(self, job_id: str, version: int) -> PipelineState:
        record = await self.storage.get_version(job_id, version)
        if not record:
            raise ValueError(f"Version {version} not found for job {job_id}")
        data = load_json(record["snapshot_path"])
        return PipelineState(**data)
