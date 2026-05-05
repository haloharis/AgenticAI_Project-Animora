import io
import os
import struct
import wave
import pytest
from unittest.mock import MagicMock, patch
from agents.audio_agent.agent import AudioAgent
from shared.schemas.pipeline_schema import (
    Story,
    Scene,
    Character,
    DialogueLine,
    Mood,
    TimingManifest,
)


def _make_silence_wav(path: str, duration_ms: int = 500):
    """Create a minimal silence WAV file at path."""
    sample_rate = 44100
    num_samples = int(sample_rate * duration_ms / 1000)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)


def _make_story(tmp_path) -> Story:
    return Story(
        id="story_test",
        title="Test Story",
        narrative="A short test.",
        style="cinematic",
        characters=[
            Character(
                id="char_001",
                name="Alice",
                description="Main character",
                voice_id="aura-asteria-en",
                personality="calm",
            )
        ],
        scenes=[
            Scene(
                id="scene_001",
                scene_number=1,
                title="Opening",
                description="The beginning.",
                mood=Mood.calm,
                duration_ms=3000,
                dialogue=[
                    DialogueLine(
                        character_id="char_001",
                        text="Hello world.",
                        emotion="neutral",
                        duration_estimate_ms=1000,
                    )
                ],
            ),
            Scene(
                id="scene_002",
                scene_number=2,
                title="Middle",
                description="The middle part.",
                mood=Mood.tense,
                duration_ms=3000,
                dialogue=[],
            ),
        ],
    )


def _tts_side_effect(tmp_path):
    """Factory: returns a side_effect fn that creates silence WAVs."""
    call_count = [0]

    def side_effect(inputs):
        call_count[0] += 1
        out_path = inputs.get("output_path", str(tmp_path / f"tts_{call_count[0]}.wav"))
        _make_silence_wav(out_path, 500)
        result = MagicMock()
        result.success = True
        result.data = {"audio_file": out_path, "duration_ms": 500}
        return result

    return side_effect


def _bgm_side_effect(tmp_path):
    call_count = [0]

    def side_effect(inputs):
        call_count[0] += 1
        out_path = inputs.get("output_path", str(tmp_path / f"bgm_{call_count[0]}.wav"))
        _make_silence_wav(out_path, inputs.get("duration_ms", 3000))
        result = MagicMock()
        result.success = True
        result.data = {"audio_file": out_path, "duration_ms": inputs.get("duration_ms", 3000)}
        return result

    return side_effect


def _merger_side_effect(tmp_path):
    call_count = [0]

    def side_effect(inputs):
        call_count[0] += 1
        out_path = inputs.get("output_path", str(tmp_path / f"merged_{call_count[0]}.wav"))
        _make_silence_wav(out_path, 3000)
        result = MagicMock()
        result.success = True
        result.data = {"audio_file": out_path, "duration_ms": 3000}
        return result

    return side_effect


@patch("agents.audio_agent.agent.AudioMergerTool")
@patch("agents.audio_agent.agent.BGMTool")
@patch("agents.audio_agent.agent.TTSTool")
def test_audio_agent_returns_manifest(MockTTS, MockBGM, MockMerger, tmp_path):
    tts_inst = MockTTS.return_value
    bgm_inst = MockBGM.return_value
    merger_inst = MockMerger.return_value

    tts_inst.safe_execute.side_effect = _tts_side_effect(tmp_path)
    bgm_inst.safe_execute.side_effect = _bgm_side_effect(tmp_path)
    merger_inst.safe_execute.side_effect = _merger_side_effect(tmp_path)

    story = _make_story(tmp_path)
    agent = AudioAgent()
    manifest = agent.run(story, job_id="job_test_001")

    assert isinstance(manifest, TimingManifest)
    assert manifest.job_id == "job_test_001"


@patch("agents.audio_agent.agent.AudioMergerTool")
@patch("agents.audio_agent.agent.BGMTool")
@patch("agents.audio_agent.agent.TTSTool")
def test_audio_agent_scene_timings(MockTTS, MockBGM, MockMerger, tmp_path):
    tts_inst = MockTTS.return_value
    bgm_inst = MockBGM.return_value
    merger_inst = MockMerger.return_value

    tts_inst.safe_execute.side_effect = _tts_side_effect(tmp_path)
    bgm_inst.safe_execute.side_effect = _bgm_side_effect(tmp_path)
    merger_inst.safe_execute.side_effect = _merger_side_effect(tmp_path)

    story = _make_story(tmp_path)
    agent = AudioAgent()
    manifest = agent.run(story, job_id="job_timing_001")

    assert len(manifest.scene_timings) == 2
    for scene_id, timing in manifest.scene_timings.items():
        assert "start_ms" in timing
        assert "end_ms" in timing
        assert timing["end_ms"] >= timing["start_ms"]


@patch("agents.audio_agent.agent.AudioMergerTool")
@patch("agents.audio_agent.agent.BGMTool")
@patch("agents.audio_agent.agent.TTSTool")
def test_audio_agent_tts_called_per_dialogue_line(MockTTS, MockBGM, MockMerger, tmp_path):
    tts_inst = MockTTS.return_value
    bgm_inst = MockBGM.return_value
    merger_inst = MockMerger.return_value

    tts_inst.safe_execute.side_effect = _tts_side_effect(tmp_path)
    bgm_inst.safe_execute.side_effect = _bgm_side_effect(tmp_path)
    merger_inst.safe_execute.side_effect = _merger_side_effect(tmp_path)

    story = _make_story(tmp_path)
    agent = AudioAgent()
    agent.run(story, job_id="job_tts_count")

    # scene_001 has 1 dialogue line; scene_002 has 0 → TTS called once
    assert tts_inst.safe_execute.call_count == 1


@patch("agents.audio_agent.agent.AudioMergerTool")
@patch("agents.audio_agent.agent.BGMTool")
@patch("agents.audio_agent.agent.TTSTool")
def test_audio_agent_sequential_timings(MockTTS, MockBGM, MockMerger, tmp_path):
    tts_inst = MockTTS.return_value
    bgm_inst = MockBGM.return_value
    merger_inst = MockMerger.return_value

    tts_inst.safe_execute.side_effect = _tts_side_effect(tmp_path)
    bgm_inst.safe_execute.side_effect = _bgm_side_effect(tmp_path)
    merger_inst.safe_execute.side_effect = _merger_side_effect(tmp_path)

    story = _make_story(tmp_path)
    agent = AudioAgent()
    manifest = agent.run(story, job_id="job_seq")

    timings = list(manifest.scene_timings.values())
    assert timings[1]["start_ms"] >= timings[0]["end_ms"]
