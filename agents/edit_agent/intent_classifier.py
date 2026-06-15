from __future__ import annotations

import json
import logging
from typing import Any, Dict

from mcp.tool_executor import ToolExecutor
from mcp.tool_registry import ToolRegistry
from shared.schemas.pipeline_schema import EditAction, EditIntent, PipelineState

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an edit intent classifier for an AI video generation system.
Given a user's edit request about their animated video, classify it into a JSON object.

Return a JSON object with these fields:
- intent: one of "audio", "video_frame", "video", "script"
- target: what to target (e.g. "all", "scene_001", "char_001", "narrator")
- scope: "single" or "all"
- parameters: dict of relevant parameters (rules per intent below)
- confidence: float between 0.0 and 1.0

Intent categories and required parameters:
- audio: changes to voice tone, BGM, volume, music style
  parameters must include "mood" (e.g. "sad", "epic", "calm")
- video_frame: changes to scene visuals, character appearance, lighting, time-of-day, color palette
  parameters MUST include "style" — a short visual description of the desired change
  (e.g. {"style": "night time, dark sky, moonlit"} or {"style": "warm golden hour lighting"})
- video: changes to the full video composition, speed, subtitles, transitions
  parameters may include "subtitles": true/false
- script: changes to dialogue, story, character lines, narrative
  parameters may include "instruction" with a short description of the change

Examples (return only valid JSON):
"Make it sadder" -> {"intent":"audio","target":"all","scope":"all","parameters":{"mood":"sad"},"confidence":0.95}
"Change scene 2 to night time" -> {"intent":"video_frame","target":"scene_2","scope":"single","parameters":{"style":"night time, dark sky, moonlit"},"confidence":0.97}
"Make all scenes darker" -> {"intent":"video_frame","target":"all","scope":"all","parameters":{"style":"dark, moody, low-key lighting"},"confidence":0.95}
"Add subtitles" -> {"intent":"video","target":"all","scope":"all","parameters":{"subtitles":true},"confidence":0.98}
"Rewrite the ending" -> {"intent":"script","target":"all","scope":"all","parameters":{"instruction":"rewrite the ending"},"confidence":0.9}"""


class IntentClassifier:
    def __init__(self) -> None:
        self.executor = ToolExecutor(ToolRegistry)

    def classify(self, query: str, pipeline_state: PipelineState) -> EditAction:
        context = self._build_context(pipeline_state)
        prompt = f"""Context about the current video:
{context}

User's edit request: "{query}"

Classify this edit request."""

        result = self.executor.run(
            "text_generator",
            {
                "prompt": prompt,
                "system_prompt": SYSTEM_PROMPT,
                "temperature": 0.2,
                "max_tokens": 512,
                "json_mode": True,
            },
        )

        if not result.success:
            return EditAction(
                intent=EditIntent.video,
                target="all",
                scope="all",
                parameters={},
                confidence=0.5,
                query=query,
            )

        try:
            data: Dict[str, Any] = json.loads(result.data) if isinstance(result.data, str) else result.data
            intent_str = data.get("intent", "video")
            intent = EditIntent(intent_str) if intent_str in EditIntent.__members__.values() else EditIntent.video
            return EditAction(
                intent=intent,
                target=data.get("target", "all"),
                scope=data.get("scope", "all"),
                parameters=data.get("parameters", {}),
                confidence=float(data.get("confidence", 0.8)),
                query=query,
            )
        except Exception as e:
            logger.warning(f"Intent classification parse error: {e}. Defaulting to video.")
            return EditAction(
                intent=EditIntent.video,
                target="all",
                scope="all",
                parameters={},
                confidence=0.5,
                query=query,
            )

    def _build_context(self, ps: PipelineState) -> str:
        lines = [f"Prompt: {ps.user_prompt}", f"Style: {ps.style}"]
        if ps.story:
            lines.append(f"Story: {ps.story.title}")
            lines.append(f"Scenes ({len(ps.story.scenes)}):")
            for s in ps.story.scenes:
                lines.append(f"  - {s.id}: {s.title} (mood: {s.mood.value})")
            lines.append(f"Characters:")
            for c in ps.story.characters:
                lines.append(f"  - {c.id}: {c.name}")
        return "\n".join(lines)
