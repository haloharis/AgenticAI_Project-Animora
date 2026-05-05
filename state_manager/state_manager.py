from __future__ import annotations

from typing import Any, Dict, List, Optional

from shared.schemas.pipeline_schema import PipelineState
from state_manager.history import HistoryManager
from state_manager.snapshot import SnapshotManager
from state_manager.storage import SQLiteStorage


class StateManager:
    _instance: Optional["StateManager"] = None

    def __init__(self, db_path: Optional[str] = None, state_dir: Optional[str] = None) -> None:
        self.storage = SQLiteStorage(db_path)
        self.snapshot_mgr = SnapshotManager(self.storage, state_dir)
        self.history_mgr = HistoryManager(self.storage)
        self._initialized = False

    @classmethod
    def get_instance(cls) -> "StateManager":
        if cls._instance is None:
            cls._instance = StateManager()
        return cls._instance

    async def initialize(self) -> None:
        if not self._initialized:
            await self.storage.init_db()
            self._initialized = True

    async def snapshot(
        self,
        pipeline_state: PipelineState,
        phase: str = "",
        note: str = "",
    ) -> PipelineState:
        pipeline_state.version += 1
        await self.snapshot_mgr.save(pipeline_state, phase=phase, note=note)
        return pipeline_state

    async def revert(self, job_id: str, version: int) -> PipelineState:
        return await self.snapshot_mgr.load(job_id, version)

    async def history(self, job_id: str) -> List[Dict[str, Any]]:
        return await self.history_mgr.get_history(job_id)

    async def get_latest(self, job_id: str) -> Optional[PipelineState]:
        record = await self.history_mgr.get_latest(job_id)
        if not record:
            return None
        return await self.snapshot_mgr.load(job_id, record["version"])
