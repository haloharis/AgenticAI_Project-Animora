from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import aiosqlite

from shared.utils.helpers import get_db_path


class SQLiteStorage:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or get_db_path()

    async def init_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    snapshot_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    phase TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
                """
            )
            await db.commit()

    async def insert_version(
        self,
        job_id: str,
        version: int,
        snapshot_path: str,
        created_at: str,
        phase: str = "",
        note: str = "",
    ) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO versions (job_id, version, snapshot_path, created_at, phase, note) VALUES (?,?,?,?,?,?)",
                (job_id, version, snapshot_path, created_at, phase, note),
            )
            await db.commit()
            return cursor.lastrowid  # type: ignore

    async def get_versions(self, job_id: str) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM versions WHERE job_id=? ORDER BY version DESC",
                (job_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_version(self, job_id: str, version: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM versions WHERE job_id=? AND version=?",
                (job_id, version),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_latest_version(self, job_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM versions WHERE job_id=? ORDER BY version DESC LIMIT 1",
                (job_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
