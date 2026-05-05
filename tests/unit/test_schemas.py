import pytest
from datetime import datetime
from shared.schemas.pipeline_schema import (
    Mood,
    PhaseStatus,
    EditIntent,
    TransitionType,
    Character,
    DialogueLine,
    Scene,
    Story,
    AudioSegment,
    TimingManifest,
    PhaseInfo,
    PipelineState,
    EditAction,
    EditResult,
)


# ── Enums ────────────────────────────────────────────────────────────────────


def test_mood_values():
    assert set(Mood.__members__.keys()) == {
        "happy", "sad", "tense", "calm", "mysterious", "epic", "romantic"
    }


def test_phase_status_values():
    assert PhaseStatus.pending == "pending"
    assert PhaseStatus.running == "running"
    assert PhaseStatus.completed == "completed"
    assert PhaseStatus.failed == "failed"


def test_edit_intent_values():
    assert set(EditIntent.__members__.keys()) == {"audio", "video_frame", "video", "script"}


# ── Character ────────────────────────────────────────────────────────────────


def test_character_defaults():
    c = Character(name="Alice", description="Main character")
    assert c.id.startswith("char_")
    assert c.voice_id == "aura-asteria-en"
    assert c.personality == ""


def test_character_custom_values():
    c = Character(
        id="char_custom",
        name="Bob",
        description="Villain",
        voice_id="aura-arcas-en",
        personality="sinister",
    )
    assert c.id == "char_custom"
    assert c.personality == "sinister"


# ── DialogueLine ─────────────────────────────────────────────────────────────


def test_dialogue_line_defaults():
    dl = DialogueLine(character_id="char_001", text="Hello")
    assert dl.emotion == "neutral"
    assert dl.duration_estimate_ms == 0


def test_dialogue_line_with_emotion():
    dl = DialogueLine(character_id="char_001", text="Run!", emotion="fearful", duration_estimate_ms=800)
    assert dl.emotion == "fearful"
    assert dl.duration_estimate_ms == 800


# ── Scene ────────────────────────────────────────────────────────────────────


def test_scene_defaults():
    s = Scene(scene_number=1, title="Opening", description="The beginning")
    assert s.id.startswith("scene_")
    assert s.mood == Mood.calm
    assert s.duration_ms == 5000
    assert s.transition == TransitionType.fade
    assert s.dialogue == []
    assert s.image_path is None


def test_scene_with_dialogue():
    dl = DialogueLine(character_id="char_001", text="Hello world")
    s = Scene(
        scene_number=1,
        title="Test",
        description="Desc",
        dialogue=[dl],
        mood=Mood.happy,
    )
    assert len(s.dialogue) == 1
    assert s.mood == Mood.happy


# ── Story ────────────────────────────────────────────────────────────────────


def test_story_defaults():
    c = Character(name="Hero", description="The hero")
    s = Scene(scene_number=1, title="S1", description="Desc")
    story = Story(title="My Story", narrative="Once upon a time.", scenes=[s], characters=[c])
    assert story.id.startswith("story_")
    assert story.style == "cinematic"
    assert story.total_duration_ms == 0


def test_story_multiple_scenes():
    chars = [Character(name=f"C{i}", description=f"Char {i}") for i in range(3)]
    scenes = [Scene(scene_number=i + 1, title=f"S{i}", description="d") for i in range(4)]
    story = Story(title="Epic", narrative="Long narrative.", scenes=scenes, characters=chars)
    assert len(story.scenes) == 4
    assert len(story.characters) == 3


# ── AudioSegment ─────────────────────────────────────────────────────────────


def test_audio_segment_defaults():
    seg = AudioSegment(scene_id="scene_001", audio_file="/tmp/test.wav")
    assert seg.segment_type == "dialogue"
    assert seg.duration_ms == 0
    assert seg.character_id is None


def test_audio_segment_bgm_type():
    seg = AudioSegment(scene_id="scene_001", audio_file="/tmp/bgm.wav", segment_type="bgm")
    assert seg.segment_type == "bgm"


# ── TimingManifest ───────────────────────────────────────────────────────────


def test_timing_manifest_empty():
    m = TimingManifest(job_id="job_001")
    assert m.segments == []
    assert m.scene_timings == {}


def test_timing_manifest_with_data():
    seg = AudioSegment(scene_id="scene_001", audio_file="/tmp/x.wav", duration_ms=3000)
    m = TimingManifest(
        job_id="job_002",
        segments=[seg],
        scene_timings={"scene_001": {"start_ms": 0, "end_ms": 3000}},
    )
    assert len(m.segments) == 1
    assert m.scene_timings["scene_001"]["end_ms"] == 3000


# ── PhaseInfo ────────────────────────────────────────────────────────────────


def test_phase_info_defaults():
    p = PhaseInfo()
    assert p.status == PhaseStatus.pending
    assert p.progress_pct == 0
    assert p.error is None
    assert p.started_at is None
    assert p.completed_at is None


def test_phase_info_with_error():
    p = PhaseInfo(status=PhaseStatus.failed, error="Connection timeout", progress_pct=40)
    assert p.status == PhaseStatus.failed
    assert p.error == "Connection timeout"
    assert p.progress_pct == 40


# ── PipelineState ─────────────────────────────────────────────────────────────


def test_pipeline_state_defaults():
    ps = PipelineState(user_prompt="A hero's journey")
    assert ps.job_id is not None and len(ps.job_id) > 0
    assert ps.style == "cinematic"
    assert ps.story is None
    assert ps.timing_manifest is None
    assert ps.final_video_path is None
    assert ps.version == 0
    assert set(ps.phases.keys()) == {"story", "audio", "video"}


def test_pipeline_state_phases_auto_populated():
    ps = PipelineState(user_prompt="Test prompt")
    for phase_name in ["story", "audio", "video"]:
        assert phase_name in ps.phases
        assert ps.phases[phase_name].status == PhaseStatus.pending


def test_pipeline_state_with_story():
    c = Character(name="Hero", description="Brave hero")
    s = Scene(scene_number=1, title="Start", description="Beginning")
    story = Story(title="T", narrative="N", scenes=[s], characters=[c])
    ps = PipelineState(user_prompt="Test", story=story, version=2)
    assert ps.story is not None
    assert ps.version == 2


# ── EditAction ────────────────────────────────────────────────────────────────


def test_edit_action_defaults():
    ea = EditAction(intent=EditIntent.audio, target="all")
    assert ea.scope == "single"
    assert ea.parameters == {}
    assert ea.confidence == 1.0


def test_edit_action_all_intents():
    for intent in EditIntent:
        ea = EditAction(intent=intent, target="scene_001", confidence=0.9)
        assert ea.intent == intent


# ── EditResult ────────────────────────────────────────────────────────────────


def test_edit_result_success():
    action = EditAction(intent=EditIntent.video, target="all")
    result = EditResult(
        job_id="job_001",
        action=action,
        success=True,
        message="Edit applied",
        new_version=3,
    )
    assert result.success is True
    assert result.new_version == 3


def test_edit_result_failure():
    action = EditAction(intent=EditIntent.script, target="all")
    result = EditResult(
        job_id="job_002",
        action=action,
        success=False,
        message="Tool failed",
    )
    assert result.success is False
    assert result.new_version == 0
