from __future__ import annotations

import uuid
from typing import Any, Dict, List, Tuple


_STYLE_TONE: dict = {
    "cinematic":  "Write a dramatic, emotionally gripping story with high stakes and compelling character arcs. Use vivid, tense dialogue and cinematic pacing.",
    "fantasy":    "Write an epic adventure set in a magical world with mythical creatures, spells, and heroic quests. Dialogue should feel grand and otherworldly.",
    "horror":     "Write a suspenseful, chilling story with a creeping sense of dread. Use ominous dialogue, dark settings, and build tension toward a terrifying climax.",
    "comedy":     "Write a light-hearted, funny story full of humour, witty banter, and comedic misunderstandings. Dialogue should make the audience laugh.",
    "sci-fi":     "Write a futuristic story involving advanced technology, space exploration, or artificial intelligence. Dialogue should feel intelligent and forward-thinking.",
    "romance":    "Write a tender love story about two characters falling for each other. Dialogue should be warm, emotionally charged, and romantic.",
}
_STYLE_TONE_DEFAULT = "Write a compelling story with engaging characters and a clear narrative arc."


def build_story_generation_prompt(user_prompt: str, style: str) -> Tuple[str, str]:
    tone_instruction = _STYLE_TONE.get(style.lower(), _STYLE_TONE_DEFAULT)
    system_prompt = (
        "You are a creative screenwriter and storyteller. "
        "Your job is to create a compelling short animated video script. "
        "Return a JSON object with the exact structure specified. "
        "Ensure all character_id references in dialogue match character ids exactly. "
        "Character descriptions are used to generate a dedicated portrait image for each character — "
        "write them as precise visual descriptions: hair color, eye color, skin tone, clothing style, "
        "height/build, and any distinguishing features. Be specific and concrete, not abstract. "
        "Scene descriptions must be rich cinematic shot directions: describe the environment, "
        "lighting, camera angle, character positions, and any action. Do not repeat character "
        "appearance details in scene descriptions — focus purely on the spatial and visual composition."
    )
    user_msg = f"""Create a short animated video script based on this idea: "{user_prompt}"

Style: {style}
Tone & genre directive: {tone_instruction}

Return a JSON object with this exact structure:
{{
  "title": "Story title",
  "narrative": "2-3 sentence overall narrative description",
  "style": "{style}",
  "characters": [
    {{
      "id": "char_001",
      "name": "Character Name",
      "role": "protagonist",
      "description": "Visual appearance only: e.g. tall young woman, long red hair, green eyes, wearing a brown leather jacket and dark jeans, small scar above left eyebrow",
      "voice_id": "aura-asteria-en",
      "personality": "personality traits"
    }}
  ],
  "scenes": [
    {{
      "id": "scene_001",
      "scene_number": 1,
      "title": "Scene title",
      "description": "Describe what is visually in the frame: setting, lighting, character positions, actions, props. Write as a camera shot description, not a narrative summary.",
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
- Make the story engaging with a clear beginning, middle, and end
- Character description must be a visual image-generation prompt (appearance only, no personality)
- Scene description must describe the visual frame content, not the narrative event
- role must be one of: protagonist, antagonist, mentor, supporting"""

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


_REALISTIC_STYLES = {"realistic", "cinematic", "live action", "documentary", "photorealistic", "real"}
_ANIME_STYLES = {"anime", "manga", "japanese animation"}
_ANIMATED_STYLES = {"animated", "cartoon", "2d animation", "pixar", "disney", "3d animation"}


def _quality_suffix(style: str) -> str:
    s = style.lower()
    if any(k in s for k in _REALISTIC_STYLES):
        return (
            "photorealistic, hyperrealistic, 8k uhd, sharp focus, "
            "DSLR photography, natural lighting, film grain, real people, "
            "not cartoon, not animated, not illustrated"
        )
    if any(k in s for k in _ANIME_STYLES):
        return (
            "anime style, highly detailed, vibrant colors, "
            "clean line art, professional anime illustration"
        )
    if any(k in s for k in _ANIMATED_STYLES):
        return (
            "3D rendered, vibrant colors, smooth shading, "
            "professional CGI animation, studio quality"
        )
    # Default: stylised digital art
    return (
        "cinematic composition, volumetric lighting, rich colors, "
        "ultra detailed, professional digital illustration"
    )


def build_visual_prompt(
    scene: Dict[str, Any], characters: List[Dict[str, Any]], style: str = ""
) -> str:
    desc = scene.get("description", "")
    mood = scene.get("mood", "calm")

    # Name + role only — no full descriptions (consistency via IP reference portraits).
    # Including the role prevents the model from mapping a name to a pop-culture character
    # (e.g. "Tom" → Tom & Jerry mouse) when subject_reference is absent.
    scene_char_ids = {d["character_id"] for d in scene.get("dialogue", [])}
    scene_chars = [c for c in characters if c["id"] in scene_char_ids]
    char_tags = ", ".join(
        f"{c['name']} ({c.get('role', 'human character')})" for c in scene_chars
    ) if scene_chars else ""

    quality = _quality_suffix(style)

    prompt = (
        desc
        + (f", featuring {char_tags}" if char_tags else "")
        + f", {mood} atmosphere, {quality}"
    )
    return prompt[:600]


def build_character_portrait_prompt(character: Dict[str, Any], style: str = "") -> str:
    desc = character.get("description", "")
    name = character.get("name", "character")
    quality = _quality_suffix(style)
    return (
        f"Full body character portrait of {name}, {desc}, "
        f"neutral studio background, character reference sheet, "
        f"centered composition, clear details, {quality}"
    )[:600]


def estimate_duration(scenes: List[Dict[str, Any]]) -> int:
    total = 0
    for scene in scenes:
        dialogue_words = sum(
            len(line.get("text", "").split())
            for line in scene.get("dialogue", [])
        )
        # LLM-supplied duration_ms is used as a floor so scenes feel at least as long as intended
        adjusted = max(dialogue_words * 70 + 2000, scene.get("duration_ms", 5000))
        scene["duration_ms"] = adjusted
        total += adjusted
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
