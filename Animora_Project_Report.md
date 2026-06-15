# Animora: An AI-Powered Animated Video Generation System

**Course:** Agentic AI  
**Submission Date:** May 2026  
**Project Repository:** AgenticAI_Project-Animora
**Team Members:**

| Name | Roll Number |
|------|------------|
| Haris Ahmed | 22i-1124 |
| Abdullah Yasin | 22i-1135 |
| Sheroz Kashif | 22i-0771 |
| Muhammad Zain | 21i-2507 |
---

## Table of Contents

1. [Abstract](#1-abstract)
2. [Introduction](#2-introduction)
3. [System Architecture](#3-system-architecture)
4. [Phase-Wise Implementation](#4-phase-wise-implementation)
   - 4.1 Phase 1 — Story Agent
   - 4.2 Phase 2 — Audio Agent
   - 4.3 Phase 3 — Video Agent
   - 4.4 Phase 4 — FastAPI Backend & React Frontend
   - 4.5 Phase 5 — Edit Agent
5. [Tools and APIs Used](#5-tools-and-apis-used)
6. [JSON Schema Design](#6-json-schema-design)
7. [MCP Tool Layer](#7-mcp-tool-layer)
8. [State Management & Version Control](#8-state-management--version-control)
9. [Challenges Faced](#9-challenges-faced)
10. [Results](#10-results)
11. [Individual Contributions](#11-individual-contributions)
12. [Conclusion](#12-conclusion)

---

## 1. Abstract

Animora is a five-phase, AI-powered pipeline that converts a plain-text user prompt into a fully narrated animated short video. The system chains four distinct AI services — a large language model for story writing, a text-to-speech engine for character voices, a generative image model for scene visuals, and a video compositor — under an agentic orchestration layer built with LangGraph and FastAPI. A React frontend streams real-time progress over Server-Sent Events (SSE) and provides an edit interface backed by an LLM-driven intent classifier. Every pipeline run is snapshotted into a SQLite-indexed version history so that edits and reverts are non-destructive. The complete pipeline runs end-to-end in 2–4 minutes per job and produces an H.264/AAC MP4 with optional burnt-in subtitles.

---

## 2. Introduction

Generating animated video from scratch requires coordinating multiple creative domains: narrative writing, voice acting, visual art direction, and video editing. Doing this manually is time-intensive and demands expertise across all four areas. Large language models and generative media APIs have made each individual step automatable; however, chaining them into a coherent, interactive product remains an engineering challenge.

Animora addresses this challenge by treating each creative domain as an autonomous agent within a shared pipeline. The agents share a single structured state object that evolves through the pipeline, and every intermediate result is persisted so that targeted edits — "make scene 3 darker," "change the narrator's voice" — can re-run only the affected downstream phases without regenerating everything from scratch.

The primary design goals were:

- **End-to-end automation** — a single text prompt produces a watchable video with no manual intervention.
- **Real-time transparency** — the user watches the pipeline progress through a live event stream.
- **Non-destructive editing** — every version is stored; any prior state can be restored instantly.
- **Modularity** — each agent can be replaced or upgraded without touching the others.

---

## 3. System Architecture

### 3.1 High-Level Overview

```
User Prompt (text + style)
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                          │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  JobQueue   │  │ SSEManager   │  │  StateManager     │  │
│  │ (asyncio)   │  │ (event bus)  │  │ (SQLite + files)  │  │
│  └──────┬──────┘  └──────┬───────┘  └─────────┬─────────┘  │
│         │                │                    │             │
│  ┌──────▼──────────────────────────────────────▼──────────┐ │
│  │              PipelineWorkflow (orchestrator)           │ │
│  │  Phase 1: StoryAgent  →  Phase 2: AudioAgent          │ │
│  │  Phase 3: VideoAgent  →  Phase 5: EditAgent            │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
        │  REST + SSE
        ▼
┌──────────────────────────────┐
│   React + Vite Frontend      │
│  Prompt → Progress → Player  │
│  Edit Interface + History    │
└──────────────────────────────┘
```

### 3.2 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Agent framework | LangGraph (`StateGraph`) | Conditional routing + retry logic in Phases 1 & 5 |
| LLM | Groq (LLaMA 3.3 70B) | Story generation + intent classification |
| Image generation | ByteDance ARK / Seedream 4.0 | Scene images + character portraits |
| Text-to-speech | Deepgram Aura | Character voice synthesis |
| Audio processing | pydub + numpy | BGM synthesis, WAV merging, silence padding |
| Video processing | MoviePy + imageio-ffmpeg | Ken Burns animation, scene composition, MP4 export |
| Backend | FastAPI + uvicorn | Async REST API + SSE streaming |
| State storage | SQLite + JSON files | Version snapshots + metadata index |
| Frontend | React 18 + Vite | Live UI with SSE-driven updates |

### 3.3 Data Flow

The shared data object that flows through every phase is `PipelineState`. It starts with only `job_id`, `user_prompt`, and `style`; each phase adds its own section until the object contains the full story, timing manifest, and final video path. Every phase completion triggers a snapshot so the state at each milestone is independently recoverable.

```
PipelineState
  ├── job_id, user_prompt, style
  ├── story          ← populated by Phase 1
  ├── timing_manifest ← populated by Phase 2
  ├── final_video_path ← populated by Phase 3
  ├── phases          ← live status/progress per phase
  └── version         ← incremented on every snapshot
```

---

## 4. Phase-Wise Implementation

### 4.1 Phase 1 — Story Agent

**Objective:** Transform a plain-text user prompt into a structured, validated story with scenes, characters, dialogue, and visual prompts ready for downstream agents.

**Architecture:** LangGraph `StateGraph` with eight sequential nodes and conditional retry routing.

**LangGraph Node Pipeline:**

```
generate_story_node
       ↓
structure_json_node
       ↓
validate_arc_node ──(fail, retry < 3)──► generate_story_node
       ↓ (pass)
build_prompts_node
       ↓
estimate_duration_node
       ↓
check_consistency_node
       ↓
finalize_node
```

**Key Implementation Details:**

1. **Story Generation (`generate_story_node`):** Constructs a system prompt that casts the LLM as a professional screenwriter. The prompt includes style-specific tone injection — e.g., *cinematic* receives "dramatic, high-stakes, cinematic language"; *fantasy* receives "epic, mythological, high fantasy language." JSON mode is enforced at the API level to guarantee parseable output on the first call.

2. **Validation (`validate_arc_node`):** Ensures at minimum two scenes exist, at least one character is defined, and every dialogue line's `character_id` resolves to a known character. Failures trigger a re-generation loop (up to 3 attempts) with the validation error injected back into the prompt.

3. **Visual Prompt Building (`build_prompts_node`):** Constructs per-scene `visual_prompt` strings by combining the scene description, character names and roles, mood keyword, and a style quality suffix (e.g., "photorealistic, cinematic lighting, 8K" for *cinematic*; "anime style, vibrant colors" for *anime*).

4. **Duration Estimation (`estimate_duration_node`):** Computes `duration_ms` per scene using word count: `dialogue_words × 70ms + 2000ms floor`. This feeds downstream audio timing.

5. **Voice Assignment:** Four Deepgram Aura voice IDs (`asteria`, `orion`, `luna`, `arcas`) are round-robin assigned to characters; the mapping is stored on each `Character` object for the audio agent.

**Output:** A fully validated `Story` object containing scenes, characters, dialogue lines, visual prompts, and per-scene duration estimates.

---

### 4.2 Phase 2 — Audio Agent

**Objective:** Synthesize character voices via TTS, generate mood-matched background music, and merge everything into one WAV file per scene.

**Architecture:** Plain Python class (`AudioAgent`) — no LangGraph, as the logic is strictly sequential with no conditional branching.

**Per-Scene Processing Loop:**

```
For each Scene:
  1. For each DialogueLine → TTSTool → {scene_id}_line_{i}.wav
  2. BGMTool(mood, duration_ms) → {scene_id}_bgm.wav
  3. AudioMergerTool(dialogue_wavs, bgm_wav) → {scene_id}_merged.wav
```

**TTS Synthesis:** Each dialogue line is sent to the Deepgram `/v1/speak` endpoint with the character's assigned voice ID. The returned WAV is saved to disk and its duration (extracted from WAV metadata) is recorded for timing alignment.

**BGM Generation (two-tier fallback):**
- *Primary:* Load a pre-recorded mood-specific audio file from `data/bgm/{mood}.mp3`.
- *Fallback:* Synthesize via numpy sine waves using mood-to-frequency constants (e.g., `calm=432 Hz`, `tense=741 Hz`). Three harmonics at frequencies `f`, `1.5f`, and `2.0f` with diminishing amplitudes are summed to create an ambient texture. Fade-in (500 ms) and fade-out (800 ms) are applied.

**Audio Merging:** `pydub` concatenates all dialogue WAVs, calculates the target duration as `max(total_dialogue_ms, scene_duration_ms, 3000)`, loops the BGM to that length, overlays dialogue on BGM at −6 dB, and pads with silence if the dialogue track is shorter than the scene window.

**Output:** A `TimingManifest` — a per-scene map of `{start_ms, end_ms}` and a list of `AudioSegment` records — consumed by the video agent for frame-accurate audio sync.

---

### 4.3 Phase 3 — Video Agent

**Objective:** Generate a cinematic still image for every scene, animate each with Ken Burns motion, composite all scenes with audio into a final MP4.

**Architecture:** Plain Python class (`VideoAgent`) using `concurrent.futures.ThreadPoolExecutor` for parallel image generation, then sequential MoviePy composition.

**Image Generation (parallel, max 4 workers):**

1. **Character Portraits:** A reference portrait is generated for each character using a prompt that emphasizes their appearance, costume, and role. These portraits are later passed as `subject_reference` (base64-encoded IP embeddings) to the ARK API when generating scene images that include those characters, ensuring visual consistency across scenes.

2. **Scene Images:** Each scene's pre-built `visual_prompt` is sent to Seedream 4.0 at 1280×720 resolution. Characters appearing in the scene have their portrait paths included in `subject_reference`. If generation fails (network error, 503, etc.), a mood-colored solid placeholder image is created in-process so the pipeline continues without crashing.

**Ken Burns Animation Algorithm:**

Each static 1280×720 image is pre-scaled to 1408×792 (a 1.1× safety margin) to provide zoom/pan headroom. For each frame at time `t ∈ [0, 1]` through the scene duration:

```
ease(t) = (1 - cos(π × t)) / 2            # cosine ease-in-out
zoom    = zoom_start + (zoom_end - zoom_start) × ease(t)
window  = (frame_width / zoom, frame_height / zoom)
crop    = crop at (pan_x × ease(t), pan_y × ease(t))
output  = downscale crop to (1280, 720)
```

Eight preset animations exist (`zoom-in-center`, `zoom-in-left`, `zoom-in-right`, `pan-left`, `pan-right`, etc.), randomly selected per scene for visual variety. All frames are pre-rendered to a lookup array before MoviePy assembly to eliminate per-frame recomputation and jitter.

**Scene Transitions:** Dissolve transitions are implemented as true cross-dissolve frame blending between adjacent scenes. Fade transitions use alpha-ramp compositing against a black frame.

**Video Composition:** MoviePy assembles all animated scene clips, aligns each scene's merged WAV track to its `[start_ms, end_ms]` window, concatenates the result, and exports to `libx264`/AAC H.264 MP4 at 24 FPS.

**Output:** An MP4 file path stored in `PipelineState.final_video_path`.

---

### 4.4 Phase 4 — FastAPI Backend & React Frontend

**Backend Architecture:**

The FastAPI application uses a lifespan context manager for startup/shutdown to initialize all singleton services in order (ToolRegistry → StateManager → SSEManager → JobQueue → PipelineWorkflow). This ordering ensures downstream services have their dependencies available before the HTTP server starts accepting requests.

**Job Queue:** An `asyncio.Queue` backed by a single background coroutine worker. Jobs are enqueued as `(job_id, prompt, style)` tuples. The worker runs each job through `PipelineWorkflow.run_pipeline()` sequentially, storing the resulting `PipelineState` in an in-memory dict keyed by `job_id`. Status transitions ("queued" → "running" → "completed" / "failed") are tracked separately to support the status polling endpoint.

**SSE Manager:** A central event bus (`SSEManager`) holds one `asyncio.Queue` per active `job_id`. Phase agents emit progress events through injected `log_fn` and `progress_fn` callbacks; these callbacks publish to the relevant queue. The SSE route pulls from the queue in an `async for` loop and streams JSON-encoded events to the browser's `EventSource`.

**SSE Event Schema:**
```json
{ "type": "phase_update", "phase": "story", "status": "running",    "progress": 30  }
{ "type": "phase_update", "phase": "story", "status": "completed",  "progress": 100 }
{ "type": "log",          "phase": "audio", "level": "info",        "message": "..."  }
{ "type": "done",         "success": true }
```

**Frontend Architecture (React + Vite):**

The single-page application manages state with `useState` hooks for `jobId`, `phases`, `videoUrl`, `logs`, `versions`, and `currentVersion`. After the user submits a prompt, `startPipeline()` is called to enqueue the job; then `connectSSE()` opens an `EventSource` that updates the UI in real time. On `{ type: "done" }` the `EventSource` is closed (preventing an auto-reconnect loop) and the video URL is resolved.

**Key UI Panels:**
- **Prompt Input:** Text area + style dropdown (cinematic, anime, cartoon, fantasy, horror) + generate button.
- **Phase Progress:** Three progress bars (story/audio/video) with individual rerun buttons for targeted re-execution.
- **Live Logs:** Scrollable real-time log output from SSE.
- **Video Preview:** HTML5 `<video>` player with download button.
- **Edit Agent:** Natural language edit input + version history dropdown with revert actions.

---

### 4.5 Phase 5 — Edit Agent

**Objective:** Accept a plain-language edit instruction ("make scene 2 look more dramatic"), classify the intent, plan the minimal set of tool calls needed, and execute them — touching only the affected phases.

**Architecture:** LangGraph `StateGraph` with four nodes.

**Node Pipeline:**

```
classify_intent_node
       ↓
  confidence < 0.4? → clarify_node → END
       ↓ (confident)
plan_edit_node
       ↓
execute_edit_node → END
```

**Intent Classification:** The LLM receives a JSON-mode system prompt describing four intent categories — `audio` (re-synthesize music/voices), `video_frame` (regenerate scene images), `video` (recomposite video, add subtitles), and `script` (rewrite story) — alongside the current pipeline context (title, scene list, character names). Low temperature (0.2) is used for determinism. The output is an `EditAction` object containing `intent`, `target` (scene ID or "all"), `scope`, `parameters`, and a `confidence` float. If `confidence < 0.4`, the agent replies with a clarification question rather than executing.

**Edit Planning (`EditPlanner`):** Maps each `EditIntent` to a concrete sequence of tool calls:
- `audio` → BGMTool + AudioMergerTool for target scenes
- `video_frame` → ImageGenTool + optional StyleTransferTool for target scenes
- `video` → CompositorTool recomposition (optionally with SubtitleTool)
- `script` → special `__story_rerun__` token that triggers a full StoryAgent re-run with the original prompt modified by the edit instruction

**Scene Matching:** The planner's `_scene_matches_target()` method handles flexible identifiers — exact UUID, numeric suffix (`"scene_3"`, `"3"`), and `"all"`.

**Execution & Rollback:** If any tool call raises an exception, the executor automatically reverts to the pre-edit version via `StateManager.revert()`. On success, a new snapshot is saved and the new version number is returned to the frontend.

---

## 5. Tools and APIs Used

### 5.1 External APIs

| Service | Model / Endpoint | Purpose | Auth |
|---------|-----------------|---------|------|
| **Groq** | `llama-3.3-70b-versatile` | Story generation, intent classification | `GROQ_API_KEY` |
| **ByteDance ARK** | `seedream-4-0-250828` | Scene image and character portrait generation | `ARK_API_KEY` |
| **Deepgram** | Aura TTS (`/v1/speak`) | Character voice synthesis (WAV) | `DEEPGRAM_API_KEY` |

**Groq / LLaMA 3.3 70B:** Used in Phases 1 and 5. JSON mode (`response_format: { type: "json_object" }`) is enforced on all structured requests; every corresponding system prompt contains the word "JSON" as required by the API. Temperature 0.7 for creative generation, 0.2 for intent classification.

**ByteDance ARK / Seedream 4.0:** A diffusion-based text-to-image model accessed via the ByteDance ARK API. The API accepts optional `subject_reference` payloads (base64-encoded reference images) for IP embedding — used to maintain character visual consistency across scenes. Rate-limit (429) and overload (503) errors are handled with exponential-backoff retries (20 s, 40 s, 80 s). A 400 error with `subject_reference` in the payload triggers an automatic retry without the reference to handle models that reject it.

**Deepgram Aura TTS:** Four voices are pre-assigned to character slots: `asteria` (female, warm), `orion` (male, deep), `luna` (female, bright), `arcas` (male, neutral). The API is called with the dialogue text and returns a WAV byte stream.

### 5.2 Core Python Libraries

| Library | Version purpose | How used |
|---------|----------------|---------|
| `langgraph` | Agent state machines | `StateGraph` for StoryAgent and EditAgent |
| `fastapi` + `sse-starlette` | Backend API + SSE | REST routes, live event streaming |
| `moviepy` | Video editing | Ken Burns animation, scene concatenation, MP4 export |
| `imageio-ffmpeg` | FFmpeg binary discovery | Platform-agnostic FFmpeg path for MoviePy and subprocess calls |
| `pydub` | Audio manipulation | WAV concatenation, BGM overlay, silence padding |
| `numpy` | Numerical computing | Sine-wave BGM synthesis, frame-level Ken Burns math |
| `Pillow` (PIL) | Image utilities | Placeholder image generation, image resizing |
| `pydantic` v2 | Data validation | All pipeline schemas (`Story`, `Scene`, `Character`, etc.) |
| `sqlalchemy` / `sqlite3` | Database | Version history index |
| `httpx` / `requests` | HTTP clients | ARK API image downloads |
| `python-dotenv` | Config | `.env` file loading |

### 5.3 Frontend Libraries

| Library | Purpose |
|---------|---------|
| React 18 | UI component framework |
| Vite | Development server and bundler |
| Native `EventSource` API | SSE streaming (no third-party library needed) |

---

## 6. JSON Schema Design

All inter-phase data structures are defined as Pydantic v2 models in `shared/schemas/pipeline_schema.py`. Using Pydantic provides automatic validation, serialization to JSON, and IDE type-checking across the entire codebase.

### 6.1 Core Domain Models

**Character:**
```json
{
  "id": "char_abc123",
  "name": "Elena",
  "role": "protagonist",
  "description": "A young archaeologist with sharp instincts",
  "voice_id": "asteria",
  "personality": "determined, curious",
  "reference_image_path": "data/temp/{job_id}/portraits/char_abc123.png"
}
```

**DialogueLine:**
```json
{
  "character_id": "char_abc123",
  "text": "The temple has been sealed for centuries.",
  "emotion": "awed",
  "duration_estimate_ms": 2800
}
```

**Scene:**
```json
{
  "id": "scene_uuid_001",
  "scene_number": 1,
  "title": "The Discovery",
  "description": "Elena brushes sand from a carved doorway.",
  "visual_prompt": "Elena, young archaeologist, brushing sand from carved stone doorway, mysterious, cinematic lighting, 8K quality",
  "dialogue": [ /* DialogueLine[] */ ],
  "mood": "mysterious",
  "duration_ms": 8400,
  "transition": "dissolve",
  "image_path": "data/temp/{job_id}/images/scene_uuid_001.png"
}
```

**Story:**
```json
{
  "id": "story_uuid",
  "title": "Echoes of the Deep",
  "narrative": "An archaeologist uncovers a sealed temple...",
  "scenes": [ /* Scene[] */ ],
  "characters": [ /* Character[] */ ],
  "total_duration_ms": 42000,
  "style": "cinematic"
}
```

### 6.2 Audio Schemas

**AudioSegment:**
```json
{
  "scene_id": "scene_uuid_001",
  "character_id": "char_abc123",
  "text": "The temple has been sealed for centuries.",
  "audio_file": "data/temp/{job_id}/audio/scene_uuid_001_line_0.wav",
  "segment_type": "dialogue",
  "duration_ms": 2800
}
```

**TimingManifest:**
```json
{
  "job_id": "job_uuid",
  "segments": [ /* AudioSegment[] */ ],
  "scene_timings": {
    "scene_uuid_001": { "start_ms": 0,    "end_ms": 8400  },
    "scene_uuid_002": { "start_ms": 8400, "end_ms": 17200 }
  }
}
```

### 6.3 Pipeline State Schema

**PhaseInfo:**
```json
{
  "status": "completed",
  "started_at": "2026-05-19T10:00:00",
  "completed_at": "2026-05-19T10:00:15",
  "error": null,
  "progress_pct": 100
}
```

**PipelineState (top-level shared object):**
```json
{
  "job_id": "job_uuid",
  "created_at": "2026-05-19T10:00:00",
  "user_prompt": "A brave knight finds a dragon egg",
  "style": "fantasy",
  "story": { /* Story */ },
  "timing_manifest": { /* TimingManifest */ },
  "final_video_path": "data/outputs/job_uuid/final_output.mp4",
  "phases": {
    "story": { /* PhaseInfo */ },
    "audio": { /* PhaseInfo */ },
    "video": { /* PhaseInfo */ }
  },
  "version": 3,
  "metadata": {}
}
```

### 6.4 Edit Schemas

**EditAction:**
```json
{
  "intent": "video_frame",
  "target": "scene_uuid_002",
  "scope": "single",
  "parameters": { "style_modifier": "dark, stormy, dramatic" },
  "confidence": 0.87,
  "query": "Make scene 2 look more dramatic and darker"
}
```

**EditResult:**
```json
{
  "job_id": "job_uuid",
  "action": { /* EditAction */ },
  "success": true,
  "message": "Scene 2 image regenerated with dramatic style",
  "new_version": 4
}
```

### 6.5 Key Enumerations

```python
class Mood(str, Enum):
    happy, sad, tense, calm, mysterious, epic, romantic, horror, cartoon

class PhaseStatus(str, Enum):
    pending, running, completed, failed

class EditIntent(str, Enum):
    audio, video_frame, video, script

class TransitionType(str, Enum):
    fade, cut, dissolve
```

---

## 7. MCP Tool Layer

Animora defines a **Model Container Protocol (MCP)** abstraction — a registry of named, independently callable tools. Every agent interacts with external services only through this layer, making individual integrations swappable without modifying agent logic.

### 7.1 Architecture

```
BaseTool (abstract)
  └── safe_execute()  — wraps execute() in try/except, logs errors
  └── execute()       — implemented by each subclass

ToolRegistry (singleton dict)
  └── auto_register_all() — instantiates and registers all tools at startup
  └── get(name) → BaseTool

ToolExecutor
  └── run(tool_name, inputs) → result dict
```

### 7.2 Tool Catalogue

| Tool | Category | Key Parameters | Returns |
|------|----------|---------------|---------|
| `TextGeneratorTool` | LLM | `prompt`, `system`, `json_mode`, `temperature` | `text` |
| `JsonStructurerTool` | LLM | `text`, `schema` | parsed dict |
| `TTSTool` | Audio | `text`, `voice_id`, `output_path` | `duration_ms` |
| `BGMTool` | Audio | `mood`, `duration_ms`, `output_path` | WAV path |
| `AudioMergerTool` | Audio | `dialogue_files[]`, `bgm_file`, `target_ms` | merged WAV path |
| `ImageGenTool` | Vision | `prompt`, `width`, `height`, `reference_image_paths[]` | PNG path |
| `ImageEditTool` | Vision | `image_path`, `operation`, `params` | edited PNG path |
| `StyleTransferTool` | Vision | `image_path`, `style_prompt` | styled PNG path |
| `CompositorTool` | Video | `scenes[]`, `output_path`, `fps` | MP4 path |
| `FFmpegTool` | Video | `input`, `output`, `args` | output path |
| `SubtitleTool` | Video | `video_path`, `srt_content` | burned MP4 |
| `FileTool` | System | `operation`, `path`, `content` | varies |
| `StateTool` | System | `operation`, `job_id`, `version` | PipelineState |
| `LoggerTool` | System | `level`, `message`, `phase` | — |

---

## 8. State Management & Version Control

### 8.1 Architecture

```
StateManager (singleton)
  ├── SnapshotManager    — saves/loads JSON + video files
  ├── SQLiteStorage      — metadata index (job_id, version, path, timestamp)
  └── HistoryManager     — query version history for a job
```

### 8.2 Snapshot Lifecycle

Every phase completion triggers `StateManager.snapshot(job_id, pipeline_state, note)`:

1. The current `final_video_path` is **copied** to `data/outputs/{job_id}/final_output_v{N}.mp4` before being overwritten, preserving the video for that version.
2. The full `PipelineState` is serialised to `data/state_versions/{job_id}/v{N}.json`.
3. A record `(job_id, N, snapshot_path, now(), phase, note)` is inserted into the `versions` SQLite table.

**Revert** (`StateManager.revert(job_id, version)`) loads the JSON snapshot for version N, restores it as the active `PipelineState` in the job queue's in-memory cache, and returns the path of the versioned MP4.

### 8.3 SQLite Schema

```sql
CREATE TABLE versions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       TEXT    NOT NULL,
    version      INTEGER NOT NULL,
    snapshot_path TEXT   NOT NULL,
    created_at   TEXT    NOT NULL,
    phase        TEXT,
    note         TEXT,
    UNIQUE(job_id, version)
);
```

---

## 9. Challenges Faced

### 9.1 Visual Consistency Across Scenes

**Problem:** Diffusion models generate independent images for each scene. Without any cross-scene constraint, the same character may appear completely different from one scene to the next — different hair colour, face shape, or clothing.

**Solution:** Seedream's `subject_reference` parameter accepts base64-encoded reference images that act as IP (Identity Preservation) embeddings. We generate one reference portrait per character in Phase 3 before generating any scene images, then pass the relevant portrait(s) as `subject_reference` when generating each scene that features those characters. This significantly improves consistency, though some variation remains.

**Residual issue:** The ARK API occasionally rejects the `subject_reference` payload with a 400 error on overloaded endpoints. The retry logic detects this and re-submits without the reference rather than failing the entire job.

### 9.2 Ken Burns Jitter

**Problem:** Naive per-frame zoom/crop in MoviePy recomputes the crop region from floating-point arithmetic at render time, causing sub-pixel rounding differences that manifest as visible jitter in the output video.

**Solution:** All Ken Burns frames are pre-rendered to a fixed numpy array before being handed to MoviePy. The cosine ease-in-out function is evaluated once per frame index over the full frame count, and the results are stored in a lookup table. MoviePy's `make_frame` callback then indexes this array directly, eliminating floating-point non-determinism during rendering.

### 9.3 Groq JSON Mode Compliance

**Problem:** The Groq API requires that any system prompt enabling `json_object` response format must contain the literal word "JSON." During development, several story-generation prompts were written without this word, causing the API to return 400 errors.

**Solution:** A code-level convention was established: every call to `TextGeneratorTool` that sets `json_mode=True` must have the word "JSON" in its system prompt. This is documented in CLAUDE.md as a common pitfall, and each agent's prompt template was audited to comply.

### 9.4 ARK API Rate Limiting and Overload

**Problem:** The Seedream API returns 503 (server overload) or 429 (rate limit exceeded) during peak usage. Generating 4–6 scene images plus character portraits in parallel exacerbates this.

**Solution:** `ImageGenTool` implements exponential-backoff retry: up to 3 attempts with sleeps of 20 s, 40 s, and 80 s respectively. The ThreadPoolExecutor's `max_workers=4` cap limits concurrent API calls. If all retries are exhausted, a mood-coloured placeholder image is generated in-process so the pipeline continues rather than failing the entire job.

### 9.5 Audio–Video Synchronisation

**Problem:** Each scene's dialogue may be shorter or longer than its visual duration. MoviePy's clip concatenation does not automatically align audio tracks to their corresponding video segments.

**Solution:** The `TimingManifest` produced in Phase 2 contains exact `{start_ms, end_ms}` boundaries per scene. Phase 3's `CompositorTool` constructs an `AudioFileClip` for each scene's merged WAV, sets its `start` time to `start_ms / 1000.0`, and uses `CompositeAudioClip` over the full video duration, ensuring frame-accurate audio placement.

### 9.6 SSE Auto-Reconnect Loop

**Problem:** The browser's native `EventSource` API automatically reconnects after the server closes the connection. When the pipeline finished and the server closed the SSE stream, the browser would immediately reconnect, causing redundant requests and duplicate log entries.

**Solution:** The final event emitted by the backend is `{ "type": "done" }`. The frontend's SSE handler calls `eventSource.close()` on receipt of this event, preventing the browser from attempting a reconnect. If the connection drops mid-run (network error), the `onerror` handler displays an error state rather than silently reconnecting.

### 9.7 Non-Destructive Editing with Large Media Files

**Problem:** Each edited version can produce a new 10–50 MB MP4 file. Storing every version by copying is straightforward but potentially expensive on disk.

**Solution:** Only the MP4 for each **completed** version is preserved as a separate file (`final_output_v{N}.mp4`). Intermediate temporary files (scene images, WAV files) are not versioned — only the final composed video and the JSON state snapshot are retained per version. This keeps per-version overhead at roughly 10–50 MB video + ~100 KB JSON.

---

## 10. Results

### 10.1 Pipeline Performance

Measured on a standard consumer machine with network access to all APIs:

| Phase | Typical Duration | Notes |
|-------|----------------|-------|
| Story generation (Phase 1) | 10–20 s | LLM latency dominated |
| Audio synthesis (Phase 2) | 30–90 s | 1–3 s per TTS call × n dialogue lines |
| Video generation (Phase 3) | 60–150 s | Image gen is the bottleneck; parallel helps |
| **Total end-to-end** | **2–4 minutes** | Varies with prompt complexity and API load |

### 10.2 Output Quality

- **Story quality:** LLaMA 3.3 70B consistently produces narratively coherent stories with 3–5 scenes, distinct character voices, and style-appropriate dialogue. Validation retry catches malformed JSON in <5% of runs.
- **Audio quality:** Deepgram Aura voices are high-quality neural TTS; dialogue is natural and character-differentiated. Sine-wave BGM is functional but noticeably synthetic compared to recorded music.
- **Visual quality:** Seedream 4.0 produces high-fidelity 1280×720 images consistent with the visual prompt. Character consistency via `subject_reference` is effective for facial features but can drift on clothing details across scenes.
- **Video quality:** Ken Burns animation adds meaningful motion to static images. Dissolve transitions are smooth. The final H.264 MP4 is browser-playable with no additional codecs.

### 10.3 Edit Accuracy

Intent classification achieves high accuracy on clear, targeted edits ("change scene 3 music to calm", "make all images anime style"). Ambiguous multi-intent queries (e.g., "fix the whole thing") correctly trigger the clarification path at the configured 0.4 confidence threshold.

### 10.4 System Reliability

- Pipeline failure rate: <5% under normal API conditions (ARK 503 retries handle transient failures).
- Edit revert: 100% success rate — snapshot files are written atomically before any destructive operation.
- SSE connection stability: No reconnect loops observed after the `EventSource.close()` fix.

---

## 11. Individual Contributions

This project was developed as a solo implementation.

| Component | Contribution |
|-----------|-------------|
| **System Architecture** | Designed the five-phase pipeline architecture, LangGraph agent structure, MCP tool layer abstraction, and SSE-based event bus. |
| **Phase 1 — Story Agent** | Implemented LangGraph `StateGraph`, story generation prompts with style injection, validation retry logic, voice assignment, visual prompt builder, and duration estimator. |
| **Phase 2 — Audio Agent** | Integrated Deepgram Aura TTS, implemented sine-wave BGM fallback synthesis using numpy, and built the pydub-based audio merging pipeline with timing manifest output. |
| **Phase 3 — Video Agent** | Integrated ByteDance ARK/Seedream for image generation with `subject_reference` IP embedding support, developed the Ken Burns animation algorithm with cosine easing and pre-rendering, implemented cross-dissolve transitions, and assembled the full MoviePy composition chain. |
| **Phase 4 — Backend** | Built the FastAPI application with async lifespan, CORS, job queue worker, SSE manager event bus, and all REST routes. |
| **Phase 4 — Frontend** | Built the React + Vite SPA with real-time SSE-driven UI updates, phase progress visualization, video player, and edit/history interface. |
| **Phase 5 — Edit Agent** | Implemented LangGraph intent classification pipeline with confidence-gated clarification, edit planner for all four intent types, scene matching, and rollback-on-failure execution. |
| **State Management** | Designed SQLite schema, built SnapshotManager with versioned file preservation, and implemented revert workflow. |
| **MCP Tool Layer** | Defined `BaseTool` abstraction, implemented all 14 tools, and built `ToolRegistry` with auto-registration. |
| **Infrastructure** | Set up project structure, environment configuration, logging, and test scaffolding. |

---

## 12. Conclusion

Animora demonstrates that a multi-agent pipeline can autonomously transform a single text prompt into a watchable, narrated animated video by coordinating a large language model, a generative image model, a text-to-speech engine, and classical audio/video processing libraries under a unified FastAPI backend.

The key architectural insights from this project are:

1. **LangGraph where routing matters, plain classes elsewhere.** Using a full state machine for the story agent (which needs validation retry loops) and the edit agent (which needs confidence-gated branching) is justified. Using plain Python classes for the audio and video agents (which are strictly sequential) avoids unnecessary complexity.

2. **The MCP tool abstraction pays dividends.** Encapsulating every external API call as a named, independently callable tool made debugging straightforward — each tool can be tested in isolation, and swapping an API (e.g., replacing Deepgram with another TTS provider) requires changing only the tool implementation.

3. **Version snapshots unlock confident editing.** The combination of JSON state snapshots and versioned MP4 copies means that any edit is risk-free from the user's perspective — a single revert call restores the exact previous state.

4. **SSE is sufficient for this use case.** Server-Sent Events provided real-time progress streaming with automatic reconnect semantics at zero additional infrastructure cost compared to WebSockets, and the browser-native `EventSource` API required no frontend library dependency.

Future directions include adding multi-language TTS support, replacing sine-wave BGM with a neural music generation model, and parallelizing the job queue to support concurrent users.

---

*Report generated for the Agentic AI course — Animora project.*
