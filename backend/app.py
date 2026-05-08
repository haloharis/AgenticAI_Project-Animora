from __future__ import annotations

import warnings
warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv", category=RuntimeWarning)

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.routes.edit_routes import router as edit_router
from backend.routes.pipeline_routes import router as pipeline_router
from backend.routes.sse_routes import router as sse_router
from backend.services.job_queue import JobQueue
from backend.services.pipeline_service import PipelineService
from backend.websocket.sse_manager import SSEManager
from shared.utils.helpers import ensure_dirs, setup_logging

load_dotenv(Path(__file__).parent.parent / ".env")
setup_logging()
logger = logging.getLogger(__name__)

_REQUIRED_ENV = ["GROQ_API_KEY", "CF_API_TOKEN", "CF_ACCOUNT_ID", "DEEPGRAM_API_KEY"]
_missing = [k for k in _REQUIRED_ENV if not os.getenv(k)]
if _missing:
    logger.warning("Missing required env vars (check .env): %s", ", ".join(_missing))

# Singletons
_sse_manager: Optional[SSEManager] = None
_job_queue: Optional[JobQueue] = None
_pipeline_service: Optional[PipelineService] = None
_workflow = None
_state_manager = None


def get_sse_manager() -> SSEManager:
    return _sse_manager  # type: ignore


def get_pipeline_service() -> PipelineService:
    return _pipeline_service  # type: ignore


def get_workflow():
    return _workflow


def get_state_manager():
    return _state_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _sse_manager, _job_queue, _pipeline_service, _workflow, _state_manager

    # Initialize directories
    output_dir = os.getenv("OUTPUT_DIR", "data/outputs")
    temp_dir = os.getenv("TEMP_DIR", "data/temp")
    state_dir = os.getenv("STATE_DIR", "data/state_versions")
    ensure_dirs(output_dir, temp_dir, state_dir)

    # Initialize MCP tools
    from mcp.tool_registry import ToolRegistry
    ToolRegistry.auto_register_all()

    # Initialize state manager
    from state_manager.state_manager import StateManager
    _state_manager = StateManager.get_instance()
    await _state_manager.initialize()

    # Initialize SSE manager
    _sse_manager = SSEManager.get_instance()

    # Initialize job queue
    _job_queue = JobQueue.get_instance()

    # Initialize workflow
    from agents.orchestrator.workflow import PipelineWorkflow
    _workflow = PipelineWorkflow(sse_manager=_sse_manager, state_manager=_state_manager)

    # Initialize pipeline service
    _pipeline_service = PipelineService(_job_queue)

    # Start worker
    def workflow_factory():
        return PipelineWorkflow(sse_manager=_sse_manager, state_manager=_state_manager)

    await _job_queue.start_worker(workflow_factory)

    logger.info("Animora API started successfully")
    yield
    logger.info("Animora API shutting down")


app = FastAPI(
    title="Animora API",
    description="AI-Powered Animated Video Generation System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173"), "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline_router, prefix="/api/pipeline", tags=["pipeline"])
app.include_router(sse_router, prefix="/api/events", tags=["events"])
app.include_router(edit_router, prefix="/api/edit", tags=["edit"])

# Serve generated video files
output_dir = os.getenv("OUTPUT_DIR", "data/outputs")
os.makedirs(output_dir, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=output_dir), name="outputs")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Animora API"}
