from __future__ import annotations

from typing import Any, Dict, List, Optional

from state_manager.storage import SQLiteStorage


class HistoryManager:
    def __init__(self, storage: SQLiteStorage) -> None:
        self.storage = storage

    async def get_history(self, job_id: str) -> List[Dict[str, Any]]:
        return await self.storage.get_versions(job_id)

    async def get_latest(self, job_id: str) -> Optional[Dict[str, Any]]:
        return await self.storage.get_latest_version(job_id)
