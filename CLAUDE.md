# Animora — Codebase Guide

## Architecture Overview

Animora is a 5-phase AI-powered animated video generation pipeline. A user submits a text prompt; the system produces a narrated MP4 video with AI-generated scenes, character voices, and ambient music.

```
User Prompt
    │
    ▼
Phase 1: Story Agent (LangGraph)
    │  Groq LLM → structured Story + Scenes + Characters
    ▼
Phase 2: Audio Agent
    │  Deepgram TTS per dialogue line + sine-wave BGM + merge
    ▼
Phase 3: Video Agent
    │  Seedream (ARK API) images + MoviePy Ken Burns animation + compose
    ▼
Phase 4: FastAPI Backend + React Frontend
    │  SSE real-time progress + edit interface + version history
    ▼
Phase 5: Edit Agent (LangGraph)
       Groq intent classification → targeted re-run of affected phases
```

## Running the Project

```bash
# Backend
pip install -r requirements.txt
cp .env.example .env        # fill in API keys
uvicorn backend.app:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | LLM text generation (LLaMA 3.3 70B) |
| `GROQ_MODEL` | Default: `llama-3.3-70b-versatile` |
| `ARK_API_KEY` | Image generation (Seedream via ByteDance ARK API) |
| `ARK_API_URL` | Default: ARK southeast endpoint |
| `ARK_MODEL` | Default: `seedream-4-0-250828` |
| `DEEPGRAM_API_KEY` | Text-to-speech (Aura voices) |
| `OUTPUT_DIR` | Where final MP4s are saved (default: `data/outputs`) |
| `TEMP_DIR` | Intermediate files (default: `data/temp`) |
| `STATE_DIR` | JSON version snapshots (default: `data/state_versions`) |
| `SQLITE_DB_PATH` | Version history DB (default: `data/animora.db`) |

## Key Design Decisions

**LangGraph only where required.** Phases 1 and 5 use LangGraph `StateGraph` for retry/conditional routing. Phases 2–3 use plain Python classes — simpler and easier to test.

**SSE over WebSocket.** Server-Sent Events via `sse-starlette` gives one-way server→client streaming with automatic reconnect; no WebSocket handshake complexity.

**File-based snapshots + SQLite index.** Each pipeline version is a JSON file in `data/state_versions/{job_id}/vN.json`. SQLite holds the metadata index (path, phase, note, timestamp) for fast history queries.

**BGM without external API.** Background music is generated from numpy sine waves using mood→frequency mapping (MOOD_BGM_FREQ in `shared/constants/constants.py`). Three harmonics at diminishing amplitudes create an ambient texture.

**ARK/Seedream retry.** The ARK API can return 503 (overload) or 429 (rate limit). `ImageGenTool` retries up to 3 times with `time.sleep(20 * attempt)`. A 400 with `subject_reference` in the payload triggers a retry without it.

**FFmpeg discovery.** `imageio_ffmpeg.get_ffmpeg_exe()` finds the bundled FFmpeg binary on any platform — no PATH dependency.

## Directory Layout

```
shared/             Pydantic schemas, constants, utility functions
mcp/                MCP tool layer (BaseTool, ToolRegistry, ToolExecutor + 11 tools)
agents/
  story_agent/      LangGraph StoryAgent — LLM → structured Story
  audio_agent/      AudioAgent — TTS + BGM + merge per scene
  video_agent/      VideoAgent — image gen + Ken Burns + compose
  edit_agent/       LangGraph EditAgent — classify intent → targeted edit
  orchestrator/     PipelineWorkflow — sequential phase runner + SSE events
state_manager/      SQLiteStorage + SnapshotManager + HistoryManager + StateManager
backend/            FastAPI app, routes, SSE manager, job queue
frontend/           React + Vite UI
data/               outputs/, temp/, state_versions/ (created at runtime)
tests/              Unit and integration tests
```

## MCP Tools Reference

| Tool | Category | Description |
|------|----------|-------------|
| `TextGeneratorTool` | llm | Groq LLaMA completion; supports `json_mode=True` |
| `JsonStructurerTool` | llm | Wraps TextGeneratorTool, retries `json.loads()` 3× |
| `TTSTool` | audio | Deepgram `/v1/speak` → WAV file |
| `BGMTool` | audio | Sine-wave ambient music generator |
| `AudioMergerTool` | audio | Concatenate dialogue + attenuate/overlay BGM |
| `ImageGenTool` | vision | Seedream via ARK API (ByteDance) → PNG; supports `subject_reference` for character IP |
| `ImageEditTool` | vision | Pillow transforms (resize/brighten/darken/crop) |
| `StyleTransferTool` | vision | Re-prompts ImageGenTool with style modifier |
| `CompositorTool` | video | MoviePy: Ken Burns ImageClip → MP4 |
| `FFmpegTool` | video | Subprocess ffmpeg compress/info |
| `SubtitleTool` | video | SRT generation + MoviePy TextClip burn-in |
| `FileTool` | system | Read/write/delete/list/exists wrappers |
| `StateTool` | system | Delegates to StateManager for snapshot/revert |
| `LoggerTool` | system | Python logging + SSE event emission |

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/pipeline/start` | Start a new job; returns `{job_id}` |
| `GET` | `/api/pipeline/{job_id}/status` | Current `PipelineState` |
| `GET` | `/api/pipeline/{job_id}/video` | Stream the final MP4 |
| `POST` | `/api/pipeline/{job_id}/rerun/{phase}` | Re-run a single phase |
| `GET` | `/api/events/{job_id}` | SSE stream of phase progress events |
| `POST` | `/api/edit` | Submit a plain-language edit query |
| `GET` | `/api/edit/{job_id}/history` | Version history list |
| `POST` | `/api/edit/{job_id}/revert/{version}` | Revert to a previous version |

## SSE Event Schema

```json
{ "type": "phase_update", "phase": "story", "status": "running", "progress": 30 }
{ "type": "phase_update", "phase": "story", "status": "completed", "progress": 100 }
{ "type": "done", "success": true }
{ "type": "done", "success": false, "error": "..." }
```

Frontend calls `es.close()` on receipt of `{ "type": "done" }` to prevent auto-reconnect loop.

## Running Tests

```bash
# Unit tests only (no API keys needed)
pytest tests/unit/ agents/ -v

# With integration tests (needs API keys in .env)
pytest --run-integration -v

# Single module
pytest tests/unit/test_state_manager.py -v
```

## Common Issues

**`ModuleNotFoundError: No module named 'mcp'`** — Run from the worktree root, not a subdirectory.

**MoviePy write fails silently** — Ensure FFmpeg is installed (`imageio-ffmpeg` bundles it) and the output directory exists.

**Groq `json_object` mode error** — Every system prompt using `json_mode=True` must contain the word "JSON". Check `TextGeneratorTool` calls.

**ARK 503/429 loops** — The Seedream API may return 503 (overload) or 429 (rate limit). `ImageGenTool` retries automatically; if it persists, wait ~60 s and resubmit.

**SSE connection stays open** — The frontend `connectSSE()` in `services/sse.js` closes the `EventSource` on `{ type: "done" }`. If it loops, check the backend is emitting that event.
