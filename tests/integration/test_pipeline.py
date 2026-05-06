"""
Integration smoke test for the full pipeline.

These tests require real API keys in .env and will make live network calls.
Run only when environment variables GROQ_API_KEY, WAVESPEED_API_KEY, DEEPGRAM_API_KEY
are set. They are skipped automatically otherwise.
"""
import os
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

pytestmark = pytest.mark.integration


@pytest.fixture
def has_api_keys():
    missing = [
        k for k in ["GROQ_API_KEY", "WAVESPEED_API_KEY", "DEEPGRAM_API_KEY"]
        if not os.environ.get(k)
    ]
    if missing:
        pytest.skip(f"Missing env vars: {', '.join(missing)}")


# ── Mocked integration: orchestrator workflow ─────────────────────────────────


@pytest.mark.asyncio
@patch("agents.video_agent.agent.CompositorTool")
@patch("agents.video_agent.agent.ImageGenTool")
@patch("agents.audio_agent.agent.AudioMergerTool")
@patch("agents.audio_agent.agent.BGMTool")
@patch("agents.audio_agent.agent.TTSTool")
@patch("agents.story_agent.agent.TextGeneratorTool")
async def test_pipeline_workflow_mocked(
    MockText, MockTTS, MockBGM, MockMerger, MockImg, MockComp, tmp_path
):
    """Full pipeline with all external APIs mocked — verifies orchestration logic."""
    import json
    from agents.orchestrator.workflow import PipelineWorkflow
    from backend.websocket.sse_manager import SSEManager

    story_json = {
        "title": "Test Pipeline Story",
        "narrative": "A short story for integration testing.",
        "characters": [
            {"id": "char_001", "name": "Hero", "description": "The hero", "voice_id": "aura-asteria-en", "personality": "brave"}
        ],
        "scenes": [
            {
                "id": "scene_001",
                "scene_number": 1,
                "title": "Beginning",
                "description": "The start.",
                "visual_prompt": "cinematic start",
                "mood": "calm",
                "duration_ms": 3000,
                "transition": "fade",
                "dialogue": [
                    {"character_id": "char_001", "text": "Hello.", "emotion": "neutral", "duration_estimate_ms": 1000}
                ],
            },
            {
                "id": "scene_002",
                "scene_number": 2,
                "title": "End",
                "description": "The conclusion.",
                "visual_prompt": "cinematic end",
                "mood": "epic",
                "duration_ms": 3000,
                "transition": "fade",
                "dialogue": [],
            },
        ],
    }

    # Text generator mock
    text_inst = MockText.return_value
    text_inst.safe_execute.return_value = MagicMock(
        success=True, data={"text": json.dumps(story_json)}
    )

    # TTS mock — create a real silence WAV
    import wave
    call_count = [0]
    def tts_se(inputs):
        call_count[0] += 1
        out = inputs.get("output_path", str(tmp_path / f"tts_{call_count[0]}.wav"))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with wave.open(out, "w") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(44100)
            wf.writeframes(b"\x00\x00" * 22050)
        return MagicMock(success=True, data={"audio_file": out, "duration_ms": 500})

    bgm_count = [0]
    def bgm_se(inputs):
        bgm_count[0] += 1
        out = inputs.get("output_path", str(tmp_path / f"bgm_{bgm_count[0]}.wav"))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with wave.open(out, "w") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(44100)
            wf.writeframes(b"\x00\x00" * 44100)
        return MagicMock(success=True, data={"audio_file": out, "duration_ms": 3000})

    merger_count = [0]
    def merger_se(inputs):
        merger_count[0] += 1
        out = inputs.get("output_path", str(tmp_path / f"merged_{merger_count[0]}.wav"))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with wave.open(out, "w") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(44100)
            wf.writeframes(b"\x00\x00" * 44100)
        return MagicMock(success=True, data={"audio_file": out, "duration_ms": 3000})

    from PIL import Image as PILImage
    img_count = [0]
    def img_se(inputs):
        img_count[0] += 1
        out = inputs.get("output_path", str(tmp_path / f"img_{img_count[0]}.png"))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        PILImage.new("RGB", (1280, 720), (50, 100, 200)).save(out)
        return MagicMock(success=True, data={"image_path": out})

    comp_count = [0]
    def comp_se(inputs):
        comp_count[0] += 1
        out = inputs.get("output_path", str(tmp_path / f"video_{comp_count[0]}.mp4"))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(b"\x00" * 256)
        return MagicMock(success=True, data={"video_path": out})

    MockTTS.return_value.safe_execute.side_effect = tts_se
    MockBGM.return_value.safe_execute.side_effect = bgm_se
    MockMerger.return_value.safe_execute.side_effect = merger_se
    MockImg.return_value.safe_execute.side_effect = img_se
    MockComp.return_value.safe_execute.side_effect = comp_se

    # Mock state manager
    from shared.schemas.pipeline_schema import PipelineState, PhaseInfo, PhaseStatus
    mock_state = PipelineState(user_prompt="integration test", job_id="job_intg_001")

    with patch("agents.orchestrator.workflow.StateManager") as MockSM:
        sm_inst = MockSM.return_value
        sm_inst.snapshot = AsyncMock(side_effect=lambda s, **kw: (setattr(s, 'version', s.version + 1) or s))
        sm_inst.get_latest = AsyncMock(return_value=None)

        sse = SSEManager()
        workflow = PipelineWorkflow(sse_manager=sse, state_manager=sm_inst)

        final_state = await workflow.run_pipeline(
            job_id="job_intg_001",
            user_prompt="A hero tests the integration pipeline",
            style="cinematic",
        )

        assert final_state is not None
        assert final_state.job_id == "job_intg_001"
