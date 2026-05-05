from __future__ import annotations

import uuid
from typing import Any, Dict, List, Tuple


def build_story_generation_prompt(user_prompt: str, style: str) -> Tuple[str, str]:
    system_prompt = (
        "You are a creative screenwriter and storyteller. "
        "Your job is to create a compelling short animated video script. "
        "Return a JSON object with the exact structure specified. "
        "Ensure all character_id references in dialogue match character ids exactly."
    )
    user_msg = f"""Create a short animated video script based on this idea: "{user_prompt}"

Style: {style}

Return a JSON object with this exact structure:
{{
  "title": "Story title",
  "narrative": "2-3 sentence overall narrative description",
  "style": "{style}",
  "characters": [
    {{
      "id": "char_001",
      "name": "Character Name",
      "description": "Physical and personality description",
      "voice_id": "aura-asteria-en",
      "personality": "personality traits"
    }}
  ],
  "scenes": [
    {{
      "id": "scene_001",
      "scene_number": 1,
      "title": "Scene title",
      "description": "Vivid scene description for visual generation",
      "visual_prompt": "",
      "mood": "calm",
      "duration_ms": 8000,
      "transition": "fade",
      "dialogue": [
        {{
          "character_id": "char_001",
          "text": "What the character says",
          "emotion": "neutral"
        }}
      ]
    }}
  ]
}}

Requirements:
- Create 3-5 scenes
- Create 2-3 characters
- Each scene must have 1-3 dialogue lines
- mood must be one of: happy, sad, tense, calm, mysterious, epic, romantic
- transition must be one of: fade, cut, dissolve
- voice_id must be one of: aura-asteria-en, aura-orion-en, aura-luna-en, aura-arcas-en
- duration_ms should be between 5000-15000 per scene
- Make the story engaging with a clear beginning, middle, and end"""

    return system_prompt, user_msg


def validate_story_arc(story_dict: Dict[str, Any]) -> Tuple[bool, str]:
    if not story_dict.get("scenes"):
        return False, "No scenes found"
    if len(story_dict["scenes"]) < 2:
        return False, "Need at least 2 scenes"
    if not story_dict.get("characters"):
        return False, "No characters found"

    char_ids = {c["id"] for c in story_dict["characters"]}
    for scene in story_dict["scenes"]:
        for line in scene.get("dialogue", []):
            cid = line.get("character_id", "")
            if cid and cid not in char_ids:
                return False, f"Unknown character_id '{cid}' in scene '{scene.get('id')}'"

    return True, "OK"


def build_visual_prompt(scene: Dict[str, Any], characters: List[Dict[str, Any]]) -> str:
    desc = scene.get("description", "")
    mood = scene.get("mood", "calm")
    style = scene.get("style", "cinematic")

    char_names = [c["name"] for c in characters]
    chars_str = ", ".join(char_names) if char_names else ""

    prompt = (
        f"{desc}"
        + (f", featuring {chars_str}" if chars_str else "")
        + f", {mood} atmosphere, cinematic lighting, high quality digital art, "
        + "detailed background, vivid colors, professional illustration"
    )
    return prompt[:500]


def estimate_duration(scenes: List[Dict[str, Any]]) -> int:
    total = 0
    for scene in scenes:
        dialogue_words = sum(
            len(line.get("text", "").split())
            for line in scene.get("dialogue", [])
        )
        total += max(dialogue_words * 70 + 2000, scene.get("duration_ms", 5000))
    return total


def check_consistency(story_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    scenes = story_dict.get("scenes", [])
    char_ids = {c["id"] for c in story_dict.get("characters", [])}

    for i, scene in enumerate(scenes):
        if scene.get("scene_number") is None:
            scene["scene_number"] = i + 1
        for line in scene.get("dialogue", []):
            if line.get("character_id") not in char_ids:
                issues.append(f"Bad character_id in scene {scene.get('id')}")

    return (len(issues) == 0, issues)


def assign_voice_ids(characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    voice_map = {
        0: "aura-asteria-en",
        1: "aura-orion-en",
        2: "aura-luna-en",
        3: "aura-arcas-en",
    }
    for i, char in enumerate(characters):
        if not char.get("voice_id"):
            char["voice_id"] = voice_map.get(i % 4, "aura-asteria-en")
    return characters


def ensure_scene_ids(story_dict: Dict[str, Any]) -> Dict[str, Any]:
    for i, scene in enumerate(story_dict.get("scenes", [])):
        if not scene.get("id"):
            scene["id"] = f"scene_{uuid.uuid4().hex[:8]}"
        scene["scene_number"] = i + 1
    for char in story_dict.get("characters", []):
        if not char.get("id"):
            char["id"] = f"char_{uuid.uuid4().hex[:8]}"
    return story_dict
