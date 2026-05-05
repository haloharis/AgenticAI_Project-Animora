import pytest
import json
from unittest.mock import MagicMock, patch
from agents.story_agent.agent import StoryAgent
from agents.story_agent.planner import (
    validate_story_arc,
    build_visual_prompt,
    estimate_duration,
    check_consistency,
    build_story_generation_prompt,
)
from shared.schemas.pipeline_schema import Story, Scene, Character, DialogueLine, Mood

VALID_STORY_JSON = {
    "title": "The Knight's Quest",
    "narrative": "A brave knight sets out to save a captured dragon.",
    "characters": [
        {
            "id": "char_001",
            "name": "Sir Roland",
            "description": "A valiant knight in shining armor",
            "voice_id": "aura-orion-en",
            "personality": "brave",
        }
    ],
    "scenes": [
        {
            "id": "scene_001",
            "scene_number": 1,
            "title": "The Journey Begins",
            "description": "Sir Roland rides through a dark forest.",
            "visual_prompt": "knight riding through dark forest, cinematic",
            "mood": "tense",
            "duration_ms": 5000,
            "transition": "fade",
            "dialogue": [
                {
                    "character_id": "char_001",
                    "text": "I must find the dragon before nightfall.",
                    "emotion": "determined",
                    "duration_estimate_ms": 2500,
                }
            ],
        },
        {
            "id": "scene_002",
            "scene_number": 2,
            "title": "The Discovery",
            "description": "Sir Roland finds the dragon trapped in a cave.",
            "visual_prompt": "dragon in cave, dramatic lighting",
            "mood": "epic",
            "duration_ms": 6000,
            "transition": "cut",
            "dialogue": [],
        },
    ],
}


def _make_mock_tool_output(json_str):
    out = MagicMock()
    out.success = True
    out.data = {"text": json_str, "content": json_str}
    return out


# ── validate_story_arc ──────────────────────────────────────────────────────


def test_validate_story_arc_valid():
    valid, msg = validate_story_arc(VALID_STORY_JSON)
    assert valid, msg


def test_validate_story_arc_no_scenes():
    data = {**VALID_STORY_JSON, "scenes": []}
    valid, msg = validate_story_arc(data)
    assert not valid
    assert "scene" in msg.lower()


def test_validate_story_arc_one_scene():
    data = {**VALID_STORY_JSON, "scenes": VALID_STORY_JSON["scenes"][:1]}
    valid, msg = validate_story_arc(data)
    assert not valid


def test_validate_story_arc_no_characters():
    data = {**VALID_STORY_JSON, "characters": []}
    valid, msg = validate_story_arc(data)
    assert not valid
    assert "character" in msg.lower()


def test_validate_story_arc_orphan_dialogue():
    bad_scene = {
        **VALID_STORY_JSON["scenes"][0],
        "dialogue": [
            {
                "character_id": "char_NONEXISTENT",
                "text": "Hello",
                "emotion": "neutral",
                "duration_estimate_ms": 0,
            }
        ],
    }
    data = {**VALID_STORY_JSON, "scenes": [bad_scene, VALID_STORY_JSON["scenes"][1]]}
    valid, msg = validate_story_arc(data)
    assert not valid


# ── build_visual_prompt ─────────────────────────────────────────────────────


def test_build_visual_prompt_contains_description():
    scene = Scene(**VALID_STORY_JSON["scenes"][0])
    chars = [Character(**VALID_STORY_JSON["characters"][0])]
    prompt = build_visual_prompt(scene, chars)
    assert isinstance(prompt, str)
    assert len(prompt) > 20


def test_build_visual_prompt_contains_mood():
    scene = Scene(**VALID_STORY_JSON["scenes"][0])
    chars = [Character(**VALID_STORY_JSON["characters"][0])]
    prompt = build_visual_prompt(scene, chars)
    assert "tense" in prompt.lower() or "atmosphere" in prompt.lower()


# ── estimate_duration ───────────────────────────────────────────────────────


def test_estimate_duration_positive():
    scenes = [Scene(**s) for s in VALID_STORY_JSON["scenes"]]
    total = estimate_duration(scenes)
    assert total > 0


def test_estimate_duration_longer_with_more_dialogue():
    scene_no_dialogue = Scene(**{**VALID_STORY_JSON["scenes"][1], "dialogue": []})
    scene_with_dialogue = Scene(**VALID_STORY_JSON["scenes"][0])
    dur_none = estimate_duration([scene_no_dialogue])
    dur_with = estimate_duration([scene_with_dialogue])
    assert dur_with >= dur_none


# ── check_consistency ───────────────────────────────────────────────────────


def test_check_consistency_valid():
    ok, issues = check_consistency(VALID_STORY_JSON)
    assert ok, issues


def test_check_consistency_duplicate_scene_numbers():
    scenes = [
        {**VALID_STORY_JSON["scenes"][0], "scene_number": 1},
        {**VALID_STORY_JSON["scenes"][1], "scene_number": 1},
    ]
    data = {**VALID_STORY_JSON, "scenes": scenes}
    ok, issues = check_consistency(data)
    assert not ok


# ── build_story_generation_prompt ────────────────────────────────────────────


def test_build_prompt_contains_json_keyword():
    prompt = build_story_generation_prompt("A hero's journey", "cinematic")
    assert "JSON" in prompt or "json" in prompt.lower()


def test_build_prompt_contains_user_prompt():
    user_prompt = "A wizard discovers a hidden portal"
    prompt = build_story_generation_prompt(user_prompt, "fantasy")
    assert user_prompt in prompt or "wizard" in prompt.lower()


# ── StoryAgent integration (mocked LLM) ─────────────────────────────────────


@patch("agents.story_agent.agent.TextGeneratorTool")
def test_story_agent_returns_story(MockTool):
    instance = MockTool.return_value
    instance.safe_execute.return_value = _make_mock_tool_output(
        json.dumps(VALID_STORY_JSON)
    )

    agent = StoryAgent()
    story = agent.run("A knight saves a dragon", "cinematic")

    assert isinstance(story, Story)
    assert len(story.scenes) >= 2
    assert len(story.characters) >= 1


@patch("agents.story_agent.agent.TextGeneratorTool")
def test_story_agent_retry_on_validation_failure(MockTool):
    bad_json = json.dumps({"title": "Bad", "narrative": "x", "scenes": [], "characters": []})
    good_json = json.dumps(VALID_STORY_JSON)

    instance = MockTool.return_value
    instance.safe_execute.side_effect = [
        _make_mock_tool_output(bad_json),
        _make_mock_tool_output(bad_json),
        _make_mock_tool_output(good_json),
    ]

    agent = StoryAgent()
    story = agent.run("Test retry", "cinematic")

    assert isinstance(story, Story)
    assert instance.safe_execute.call_count == 3


@patch("agents.story_agent.agent.TextGeneratorTool")
def test_story_agent_raises_after_max_retries(MockTool):
    bad_json = json.dumps({"title": "Bad", "narrative": "x", "scenes": [], "characters": []})

    instance = MockTool.return_value
    instance.safe_execute.return_value = _make_mock_tool_output(bad_json)

    agent = StoryAgent()
    with pytest.raises(Exception):
        agent.run("Always fails", "cinematic")
