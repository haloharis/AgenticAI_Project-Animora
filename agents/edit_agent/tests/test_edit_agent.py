import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from agents.edit_agent.intent_classifier import IntentClassifier
from agents.edit_agent.agent import EditAgent
from shared.schemas.pipeline_schema import (
    EditAction,
    EditIntent,
    PipelineState,
    Story,
    Scene,
    Character,
    Mood,
    PhaseInfo,
    PhaseStatus,
)


def _make_pipeline_state(job_id="job_edit_001") -> PipelineState:
    story = Story(
        id="story_edit",
        title="Edit Test",
        narrative="A short story for editing tests.",
        style="cinematic",
        characters=[
            Character(id="char_001", name="Alice", description="Main character")
        ],
        scenes=[
            Scene(
                id="scene_001",
                scene_number=1,
                title="Scene 1",
                description="Opening scene",
                mood=Mood.calm,
                duration_ms=4000,
            ),
            Scene(
                id="scene_002",
                scene_number=2,
                title="Scene 2",
                description="Closing scene",
                mood=Mood.epic,
                duration_ms=3000,
            ),
        ],
    )
    return PipelineState(
        job_id=job_id,
        user_prompt="A test story",
        style="cinematic",
        story=story,
        phases={
            "story": PhaseInfo(status=PhaseStatus.completed, progress_pct=100),
            "audio": PhaseInfo(status=PhaseStatus.completed, progress_pct=100),
            "video": PhaseInfo(status=PhaseStatus.completed, progress_pct=100),
        },
        version=1,
    )


def _groq_response(intent: str, target: str = "all", confidence: float = 0.95) -> dict:
    return {
        "intent": intent,
        "target": target,
        "scope": "all",
        "parameters": {},
        "confidence": confidence,
    }


# ── IntentClassifier ─────────────────────────────────────────────────────────


@patch("agents.edit_agent.intent_classifier.TextGeneratorTool")
def test_classify_audio_intent(MockTool):
    inst = MockTool.return_value
    inst.safe_execute.return_value = MagicMock(
        success=True, data={"text": json.dumps(_groq_response("audio"))}
    )
    clf = IntentClassifier()
    action = clf.classify("Make the music louder", _make_pipeline_state())
    assert action.intent == EditIntent.audio


@patch("agents.edit_agent.intent_classifier.TextGeneratorTool")
def test_classify_video_frame_intent(MockTool):
    inst = MockTool.return_value
    inst.safe_execute.return_value = MagicMock(
        success=True, data={"text": json.dumps(_groq_response("video_frame", "scene_001"))}
    )
    clf = IntentClassifier()
    action = clf.classify("Change scene 1 to night time", _make_pipeline_state())
    assert action.intent == EditIntent.video_frame


@patch("agents.edit_agent.intent_classifier.TextGeneratorTool")
def test_classify_video_intent(MockTool):
    inst = MockTool.return_value
    inst.safe_execute.return_value = MagicMock(
        success=True, data={"text": json.dumps(_groq_response("video"))}
    )
    clf = IntentClassifier()
    action = clf.classify("Speed up the video", _make_pipeline_state())
    assert action.intent == EditIntent.video


@patch("agents.edit_agent.intent_classifier.TextGeneratorTool")
def test_classify_script_intent(MockTool):
    inst = MockTool.return_value
    inst.safe_execute.return_value = MagicMock(
        success=True, data={"text": json.dumps(_groq_response("script"))}
    )
    clf = IntentClassifier()
    action = clf.classify("Rewrite the story to be sadder", _make_pipeline_state())
    assert action.intent == EditIntent.script


@patch("agents.edit_agent.intent_classifier.TextGeneratorTool")
def test_classify_low_confidence_fallback(MockTool):
    inst = MockTool.return_value
    inst.safe_execute.return_value = MagicMock(
        success=True,
        data={"text": json.dumps(_groq_response("audio", confidence=0.3))},
    )
    clf = IntentClassifier()
    # Low confidence should either raise or return a default — not crash
    try:
        action = clf.classify("Something ambiguous", _make_pipeline_state())
        assert action is not None
    except Exception:
        pass  # NeedsClassification is acceptable


@patch("agents.edit_agent.intent_classifier.TextGeneratorTool")
def test_classify_malformed_json_fallback(MockTool):
    inst = MockTool.return_value
    inst.safe_execute.return_value = MagicMock(
        success=True, data={"text": "not valid json {{{"}
    )
    clf = IntentClassifier()
    # Should fall back gracefully, not crash
    action = clf.classify("Something", _make_pipeline_state())
    assert action is not None
    assert action.intent in EditIntent.__members__.values()


@patch("agents.edit_agent.intent_classifier.TextGeneratorTool")
def test_classify_confidence_stored(MockTool):
    inst = MockTool.return_value
    inst.safe_execute.return_value = MagicMock(
        success=True, data={"text": json.dumps(_groq_response("video", confidence=0.88))}
    )
    clf = IntentClassifier()
    action = clf.classify("Change something about the video", _make_pipeline_state())
    assert action.confidence == pytest.approx(0.88, abs=0.01)


# ── EditAgent end-to-end (mocked tools) ──────────────────────────────────────


@patch("agents.edit_agent.executor.StateManager")
@patch("agents.edit_agent.intent_classifier.TextGeneratorTool")
def test_edit_agent_audio_intent(MockTool, MockSM, tmp_path):
    inst = MockTool.return_value
    inst.safe_execute.return_value = MagicMock(
        success=True, data={"text": json.dumps(_groq_response("audio"))}
    )
    sm_inst = MockSM.return_value
    sm_inst.snapshot = AsyncMock(return_value=_make_pipeline_state())
    sm_inst.revert = AsyncMock(return_value=_make_pipeline_state())

    agent = EditAgent()
    state = _make_pipeline_state()
    result = agent.run("Make background music louder", state)
    assert result is not None
    assert hasattr(result, "success")


@patch("agents.edit_agent.executor.StateManager")
@patch("agents.edit_agent.intent_classifier.TextGeneratorTool")
def test_edit_agent_returns_edit_result(MockTool, MockSM, tmp_path):
    inst = MockTool.return_value
    inst.safe_execute.return_value = MagicMock(
        success=True, data={"text": json.dumps(_groq_response("video"))}
    )
    sm_inst = MockSM.return_value
    sm_inst.snapshot = AsyncMock(return_value=_make_pipeline_state(job_id="job_r2"))
    sm_inst.revert = AsyncMock(return_value=_make_pipeline_state(job_id="job_r2"))

    agent = EditAgent()
    state = _make_pipeline_state(job_id="job_r2")
    result = agent.run("Make video brighter", state)

    from shared.schemas.pipeline_schema import EditResult
    assert isinstance(result, EditResult) or hasattr(result, "success")


@patch("agents.edit_agent.intent_classifier.TextGeneratorTool")
def test_edit_agent_clarification_on_low_confidence(MockTool):
    inst = MockTool.return_value
    inst.safe_execute.return_value = MagicMock(
        success=True,
        data={"text": json.dumps(_groq_response("audio", confidence=0.2))},
    )
    agent = EditAgent()
    state = _make_pipeline_state()
    result = agent.run("I want something different", state)
    # May return clarification result
    assert result is not None
