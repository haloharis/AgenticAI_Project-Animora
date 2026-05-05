import os
import pytest
from unittest.mock import MagicMock, patch
from agents.video_agent.agent import VideoAgent
from shared.schemas.pipeline_schema import (
    Story,
    Scene,
    Character,
    DialogueLine,
    Mood,
    TimingManifest,
    AudioSegment,
)


def _make_story() -> Story:
    return Story(
        id="story_vid",
        title="Video Test Story",
        narrative="Short test narrative.",
        style="cinematic",
        characters=[
            Character(
                id="char_001",
                name="Hero",
                description="The main hero",
                voice_id="aura-asteria-en",
            )
        ],
        scenes=[
            Scene(
                id="scene_001",
                scene_number=1,
                title="Scene One",
                description="First scene description",
                mood=Mood.epic,
                duration_ms=4000,
            ),
            Scene(
                id="scene_002",
                scene_number=2,
                title="Scene Two",
                description="Second scene description",
                mood=Mood.calm,
                duration_ms=3000,
            ),
        ],
    )


def _make_manifest(tmp_path) -> TimingManifest:
    merged1 = tmp_path / "scene_001_merged.wav"
    merged2 = tmp_path / "scene_002_merged.wav"
    merged1.write_bytes(b"RIFF" + b"\x00" * 40)
    merged2.write_bytes(b"RIFF" + b"\x00" * 40)
    return TimingManifest(
        job_id="job_vid_001",
        segments=[
            AudioSegment(
                scene_id="scene_001",
                audio_file=str(merged1),
                segment_type="merged",
                duration_ms=4000,
            ),
            AudioSegment(
                scene_id="scene_002",
                audio_file=str(merged2),
                segment_type="merged",
                duration_ms=3000,
            ),
        ],
        scene_timings={
            "scene_001": {"start_ms": 0, "end_ms": 4000},
            "scene_002": {"start_ms": 4000, "end_ms": 7000},
        },
    )


def _image_gen_side_effect(tmp_path):
    call_count = [0]

    def side_effect(inputs):
        call_count[0] += 1
        out_path = inputs.get("output_path", str(tmp_path / f"img_{call_count[0]}.png"))
        # create a minimal PNG-like stub
        from PIL import Image
        img = Image.new("RGB", (1280, 720), color=(100, 100, 200))
        img.save(out_path)
        result = MagicMock()
        result.success = True
        result.data = {"image_path": out_path}
        return result

    return side_effect


def _compositor_side_effect(tmp_path):
    def side_effect(inputs):
        out_path = inputs.get("output_path", str(tmp_path / "output.mp4"))
        # create stub MP4 file
        with open(out_path, "wb") as f:
            f.write(b"\x00" * 128)
        result = MagicMock()
        result.success = True
        result.data = {"video_path": out_path}
        return result

    return side_effect


@patch("agents.video_agent.agent.CompositorTool")
@patch("agents.video_agent.agent.ImageGenTool")
def test_video_agent_returns_path(MockImageGen, MockCompositor, tmp_path):
    img_inst = MockImageGen.return_value
    comp_inst = MockCompositor.return_value

    img_inst.safe_execute.side_effect = _image_gen_side_effect(tmp_path)
    comp_inst.safe_execute.side_effect = _compositor_side_effect(tmp_path)

    story = _make_story()
    manifest = _make_manifest(tmp_path)
    agent = VideoAgent()
    video_path = agent.run(story, manifest, job_id="job_vid_001")

    assert isinstance(video_path, str)
    assert len(video_path) > 0


@patch("agents.video_agent.agent.CompositorTool")
@patch("agents.video_agent.agent.ImageGenTool")
def test_video_agent_image_gen_called_per_scene(MockImageGen, MockCompositor, tmp_path):
    img_inst = MockImageGen.return_value
    comp_inst = MockCompositor.return_value

    img_inst.safe_execute.side_effect = _image_gen_side_effect(tmp_path)
    comp_inst.safe_execute.side_effect = _compositor_side_effect(tmp_path)

    story = _make_story()
    manifest = _make_manifest(tmp_path)
    agent = VideoAgent()
    agent.run(story, manifest, job_id="job_vid_002")

    assert img_inst.safe_execute.call_count == 2


@patch("agents.video_agent.agent.CompositorTool")
@patch("agents.video_agent.agent.ImageGenTool")
def test_video_agent_compositor_called_once(MockImageGen, MockCompositor, tmp_path):
    img_inst = MockImageGen.return_value
    comp_inst = MockCompositor.return_value

    img_inst.safe_execute.side_effect = _image_gen_side_effect(tmp_path)
    comp_inst.safe_execute.side_effect = _compositor_side_effect(tmp_path)

    story = _make_story()
    manifest = _make_manifest(tmp_path)
    agent = VideoAgent()
    agent.run(story, manifest, job_id="job_vid_003")

    assert comp_inst.safe_execute.call_count == 1


@patch("agents.video_agent.agent.CompositorTool")
@patch("agents.video_agent.agent.ImageGenTool")
def test_video_agent_fallback_placeholder_on_image_fail(MockImageGen, MockCompositor, tmp_path):
    img_inst = MockImageGen.return_value
    comp_inst = MockCompositor.return_value

    # Image gen always fails
    fail_result = MagicMock()
    fail_result.success = False
    fail_result.error = "503 Service Unavailable"
    img_inst.safe_execute.return_value = fail_result

    comp_inst.safe_execute.side_effect = _compositor_side_effect(tmp_path)

    story = _make_story()
    manifest = _make_manifest(tmp_path)
    agent = VideoAgent()
    # Should not raise — uses placeholder images
    video_path = agent.run(story, manifest, job_id="job_fallback")
    assert isinstance(video_path, str)
