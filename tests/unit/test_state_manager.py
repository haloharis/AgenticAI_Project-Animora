import os
import json
import asyncio
import pytest
import pytest_asyncio
from pathlib import Path
from state_manager.storage import SQLiteStorage
from state_manager.snapshot import SnapshotManager
from state_manager.history import HistoryManager
from state_manager.state_manager import StateManager
from shared.schemas.pipeline_schema import (
    PipelineState,
    PhaseInfo,
    PhaseStatus,
)


def _make_state(job_id: str, version: int = 0) -> PipelineState:
    return PipelineState(
        job_id=job_id,
        user_prompt="Test prompt",
        style="cinematic",
        version=version,
        phases={
            "story": PhaseInfo(status=PhaseStatus.completed, progress_pct=100),
            "audio": PhaseInfo(status=PhaseStatus.completed, progress_pct=100),
            "video": PhaseInfo(status=PhaseStatus.completed, progress_pct=100),
        },
    )


# ── SQLiteStorage ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sqlite_storage_insert_and_get(tmp_path):
    db_path = str(tmp_path / "test.db")
    storage = SQLiteStorage(db_path=db_path)
    await storage.init_db()

    snapshot_path = str(tmp_path / "v1.json")
    Path(snapshot_path).write_text("{}")

    await storage.insert_version(
        job_id="job_001",
        version=1,
        snapshot_path=snapshot_path,
        phase="story",
        note="Initial snapshot",
    )

    row = await storage.get_version("job_001", 1)
    assert row is not None
    assert row["version"] == 1
    assert row["phase"] == "story"


@pytest.mark.asyncio
async def test_sqlite_storage_get_versions(tmp_path):
    db_path = str(tmp_path / "test2.db")
    storage = SQLiteStorage(db_path=db_path)
    await storage.init_db()

    for i in range(1, 4):
        snap = str(tmp_path / f"v{i}.json")
        Path(snap).write_text("{}")
        await storage.insert_version(
            job_id="job_002", version=i, snapshot_path=snap, phase="story", note=f"v{i}"
        )

    versions = await storage.get_versions("job_002")
    assert len(versions) == 3


@pytest.mark.asyncio
async def test_sqlite_storage_get_latest(tmp_path):
    db_path = str(tmp_path / "test3.db")
    storage = SQLiteStorage(db_path=db_path)
    await storage.init_db()

    for i in range(1, 5):
        snap = str(tmp_path / f"v{i}.json")
        Path(snap).write_text("{}")
        await storage.insert_version(
            job_id="job_003", version=i, snapshot_path=snap, phase="video", note=f"v{i}"
        )

    latest = await storage.get_latest_version("job_003")
    assert latest is not None
    assert latest["version"] == 4


@pytest.mark.asyncio
async def test_sqlite_storage_missing_job(tmp_path):
    db_path = str(tmp_path / "test4.db")
    storage = SQLiteStorage(db_path=db_path)
    await storage.init_db()

    versions = await storage.get_versions("nonexistent_job")
    assert versions == []

    latest = await storage.get_latest_version("nonexistent_job")
    assert latest is None


# ── SnapshotManager ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_snapshot_save_creates_file(tmp_path):
    db_path = str(tmp_path / "snap.db")
    state_dir = str(tmp_path / "snapshots")
    storage = SQLiteStorage(db_path=db_path)
    await storage.init_db()

    manager = SnapshotManager(storage=storage, state_dir=state_dir)
    state = _make_state("job_snap_001", version=1)

    saved_path = await manager.save(state, phase="story", note="test save")
    assert os.path.exists(saved_path)

    content = json.loads(Path(saved_path).read_text())
    assert content["job_id"] == "job_snap_001"


@pytest.mark.asyncio
async def test_snapshot_load_roundtrip(tmp_path):
    db_path = str(tmp_path / "roundtrip.db")
    state_dir = str(tmp_path / "snapshots")
    storage = SQLiteStorage(db_path=db_path)
    await storage.init_db()

    manager = SnapshotManager(storage=storage, state_dir=state_dir)
    original = _make_state("job_snap_002", version=1)
    original.metadata["test_key"] = "test_value"

    await manager.save(original, phase="audio", note="roundtrip")
    loaded = await manager.load("job_snap_002", 1)

    assert loaded.job_id == "job_snap_002"
    assert loaded.metadata.get("test_key") == "test_value"


# ── StateManager ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_state_manager_snapshot_increments_version(tmp_path):
    db_path = str(tmp_path / "sm.db")
    state_dir = str(tmp_path / "sm_snapshots")

    sm = StateManager.__new__(StateManager)
    sm._storage = SQLiteStorage(db_path=db_path)
    sm._snapshot_manager = SnapshotManager(storage=sm._storage, state_dir=state_dir)
    sm._history_manager = HistoryManager(storage=sm._storage)
    await sm._storage.init_db()

    state_v0 = _make_state("job_sm_001", version=0)
    state_v1 = await sm.snapshot(state_v0, phase="story", note="first")
    assert state_v1.version == 1

    state_v2 = await sm.snapshot(state_v1, phase="audio", note="second")
    assert state_v2.version == 2


@pytest.mark.asyncio
async def test_state_manager_revert(tmp_path):
    db_path = str(tmp_path / "revert.db")
    state_dir = str(tmp_path / "revert_snapshots")

    sm = StateManager.__new__(StateManager)
    sm._storage = SQLiteStorage(db_path=db_path)
    sm._snapshot_manager = SnapshotManager(storage=sm._storage, state_dir=state_dir)
    sm._history_manager = HistoryManager(storage=sm._storage)
    await sm._storage.init_db()

    state = _make_state("job_revert_001", version=0)
    state.metadata["marker"] = "v1_data"

    v1 = await sm.snapshot(state, phase="story", note="v1")
    assert v1.version == 1

    v1.metadata["marker"] = "v2_data"
    v2 = await sm.snapshot(v1, phase="audio", note="v2")
    assert v2.version == 2

    reverted = await sm.revert("job_revert_001", 1)
    assert reverted.version == 1
    assert reverted.metadata.get("marker") == "v1_data"


@pytest.mark.asyncio
async def test_state_manager_history_sorted_desc(tmp_path):
    db_path = str(tmp_path / "hist.db")
    state_dir = str(tmp_path / "hist_snapshots")

    sm = StateManager.__new__(StateManager)
    sm._storage = SQLiteStorage(db_path=db_path)
    sm._snapshot_manager = SnapshotManager(storage=sm._storage, state_dir=state_dir)
    sm._history_manager = HistoryManager(storage=sm._storage)
    await sm._storage.init_db()

    state = _make_state("job_hist_001", version=0)
    for i in range(3):
        state = await sm.snapshot(state, phase="story", note=f"snap_{i}")

    history = await sm.history("job_hist_001")
    assert len(history) == 3
    versions = [h["version"] for h in history]
    assert versions == sorted(versions, reverse=True)


@pytest.mark.asyncio
async def test_state_manager_get_latest(tmp_path):
    db_path = str(tmp_path / "latest.db")
    state_dir = str(tmp_path / "latest_snapshots")

    sm = StateManager.__new__(StateManager)
    sm._storage = SQLiteStorage(db_path=db_path)
    sm._snapshot_manager = SnapshotManager(storage=sm._storage, state_dir=state_dir)
    sm._history_manager = HistoryManager(storage=sm._storage)
    await sm._storage.init_db()

    latest = await sm.get_latest("job_no_history")
    assert latest is None

    state = _make_state("job_latest_001", version=0)
    await sm.snapshot(state, phase="story", note="first")
    state2 = _make_state("job_latest_001", version=1)
    state2.metadata["final"] = True
    await sm.snapshot(state2, phase="video", note="final")

    result = await sm.get_latest("job_latest_001")
    assert result is not None
    assert result.version == 2
