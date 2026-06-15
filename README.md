# Animora

AI-powered animated video generation from a single text prompt. Type a story idea, get a narrated MP4 video with AI-generated scenes, character voices, and ambient music.

## Demo

```
Prompt: "A small dragon discovers fire for the first time in an enchanted forest"
Style:  Fantasy
Output: 30-second animated MP4 with narrated scenes, ambient music, character dialogue
```

## Features

- **Story generation** — LLaMA 3.3 70B builds a structured multi-scene narrative with characters and dialogue
- **AI voice synthesis** — Deepgram Aura TTS gives each character a distinct voice
- **Scene images** — Seedream (ByteDance ARK API) generates cinematic visuals per scene
- **Ken Burns animation** — Subtle zoom/pan gives static images motion
- **Ambient BGM** — Mood-matched background music synthesized from sine waves
- **Real-time progress** — SSE stream shows each pipeline phase as it runs
- **Plain-language edits** — Describe changes in natural language; the edit agent re-runs only the affected phases
- **Version history** — Every edit creates a snapshot; revert to any previous version

## Prerequisites

- Python 3.11+
- Node.js 18+
- API keys for: [Groq](https://console.groq.com), [ByteDance ARK](https://www.volcengine.com/product/ark), [Deepgram](https://console.deepgram.com)

## Quick Start

### 1. Clone and set up Python environment

```bash
git clone <repo-url>
cd <repo-dir>
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```
GROQ_API_KEY=your_groq_key_here
ARK_API_KEY=your_ark_api_key_here
ARK_MODEL=seedream-4-0-250828
DEEPGRAM_API_KEY=your_deepgram_key_here
```

### 3. Start the backend

```bash
uvicorn backend.app:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

### 4. Start the frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

## Usage

1. Type a story prompt in the text area
2. Select a visual style (Cinematic, Fantasy, Horror, Comedy, Sci-Fi, Romance)
3. Click **Generate**
4. Watch the pipeline progress bars (Story → Audio → Video)
5. When complete, preview and download the MP4
6. Use the **Edit** box to describe changes in plain language, e.g.:
   - *"Make scene 2 feel more dramatic"*
   - *"Change the background music to something happier"*
   - *"Add subtitles"*
7. Use **Version History** to revert to any previous state

## Project Structure

```
shared/         Pydantic data models, constants, utility functions
mcp/            Tool abstraction layer (11 tools across 5 categories)
agents/
  story_agent/  LangGraph pipeline — LLM → structured Story object
  audio_agent/  TTS + BGM synthesis + audio merging
  video_agent/  Image generation + Ken Burns + video composition
  edit_agent/   LangGraph pipeline — intent classification → targeted edit
  orchestrator/ Sequential phase runner with SSE progress emission
state_manager/  SQLite-backed version history and JSON snapshots
backend/        FastAPI REST API + SSE streaming
frontend/       React + Vite user interface
data/           Runtime outputs, temp files, state snapshots (auto-created)
tests/          Unit and integration tests
```

## Running Tests

```bash
# All unit tests (no API keys required)
pytest tests/unit/ agents/ -v

# Skip integration tests explicitly
pytest tests/unit/ agents/ -v -m "not integration"

# Coverage report
pytest tests/unit/ agents/ --cov=. --cov-report=term-missing
```

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/pipeline/start` | POST | Start pipeline; body `{prompt, style}`; returns `{job_id}` |
| `/api/pipeline/{job_id}/status` | GET | Full pipeline state JSON |
| `/api/pipeline/{job_id}/video` | GET | Stream final MP4 |
| `/api/pipeline/{job_id}/rerun/{phase}` | POST | Re-run one phase |
| `/api/events/{job_id}` | GET | SSE stream of phase progress |
| `/api/edit` | POST | Submit edit; body `{job_id, query}` |
| `/api/edit/{job_id}/history` | GET | Version list |
| `/api/edit/{job_id}/revert/{version}` | POST | Revert to version |

## Technology Stack

| Layer | Technology |
|-------|-----------|
| LLM | Groq — LLaMA 3.3 70B Versatile |
| Image generation | ByteDance ARK — Seedream (`seedream-4-0-250828`) |
| Text-to-speech | Deepgram — Aura |
| Video composition | MoviePy + FFmpeg |
| Agent orchestration | LangGraph |
| Backend | FastAPI + uvicorn |
| Frontend | React 18 + Vite |
| State persistence | SQLite + JSON snapshots |
| Streaming | Server-Sent Events (SSE) |

## Troubleshooting

**Image generation returns 503 or 429** — The ARK/Seedream API may be overloaded or rate-limiting. `ImageGenTool` retries automatically up to 3 times with back-off. If it persists, wait ~60 seconds and resubmit.

**No audio in video** — Ensure FFmpeg is installed. The `imageio-ffmpeg` package bundles a binary; if MoviePy still can't find it, install FFmpeg system-wide.

**Frontend shows no video after pipeline completes** — Check that the backend is running on port 8000 and the Vite proxy in `frontend/vite.config.js` is configured correctly.

**`ModuleNotFoundError`** — Always run backend commands from the project root directory, not a subdirectory.
