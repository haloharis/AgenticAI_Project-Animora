from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from agents.story_agent.planner import (
    assign_voice_ids,
    build_story_generation_prompt,
    build_visual_prompt,
    check_consistency,
    ensure_scene_ids,
    estimate_duration,
    validate_story_arc,
)
from mcp.tool_executor import ToolExecutor
from mcp.tool_registry import ToolRegistry
from shared.schemas.pipeline_schema import Story

logger = logging.getLogger(__name__)


class StoryState(TypedDict):
    user_prompt: str
    style: str
    raw_story_text: str
    story_dict: Dict[str, Any]
    validation_passed: bool
    retry_count: int
    errors: List[str]
    story: Optional[Dict[str, Any]]


class StoryAgent:
    def __init__(self) -> None:
        self.executor = ToolExecutor(ToolRegistry)
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        g = StateGraph(StoryState)

        g.add_node("generate_story", self._generate_story_node)
        g.add_node("structure_json", self._structure_json_node)
        g.add_node("validate_arc", self._validate_arc_node)
        g.add_node("build_prompts", self._build_prompts_node)
        g.add_node("estimate_duration", self._estimate_duration_node)
        g.add_node("check_consistency", self._check_consistency_node)
        g.add_node("finalize", self._finalize_node)

        g.set_entry_point("generate_story")
        g.add_edge("generate_story", "structure_json")
        g.add_edge("structure_json", "validate_arc")
        g.add_conditional_edges(
            "validate_arc",
            self._route_after_validation,
            {
                "retry": "generate_story",
                "proceed": "build_prompts",
                "fail": END,
            },
        )
        g.add_edge("build_prompts", "estimate_duration")
        g.add_edge("estimate_duration", "check_consistency")
        g.add_edge("check_consistency", "finalize")
        g.add_edge("finalize", END)

        return g.compile()

    def _generate_story_node(self, state: StoryState) -> Dict[str, Any]:
        logger.info("Generating story...")
        system_prompt, user_msg = build_story_generation_prompt(
            state["user_prompt"], state["style"]
        )
        result = self.executor.run(
            "text_generator",
            {
                "prompt": user_msg,
                "system_prompt": system_prompt,
                "temperature": 0.8,
                "max_tokens": 4096,
                "json_mode": True,
            },
        )
        raw_text = result.data if result.success else "{}"
        return {
            "raw_story_text": raw_text,
            "retry_count": state.get("retry_count", 0),
        }

    def _structure_json_node(self, state: StoryState) -> Dict[str, Any]:
        raw = state.get("raw_story_text", "{}")
        try:
            story_dict = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            story_dict = {}
        story_dict = ensure_scene_ids(story_dict)
        story_dict["characters"] = assign_voice_ids(story_dict.get("characters", []))
        return {"story_dict": story_dict}

    def _validate_arc_node(self, state: StoryState) -> Dict[str, Any]:
        passed, msg = validate_story_arc(state.get("story_dict", {}))
        return {
            "validation_passed": passed,
            "errors": [] if passed else [msg],
        }

    def _route_after_validation(self, state: StoryState) -> str:
        if state["validation_passed"]:
            return "proceed"
        retry_count = state.get("retry_count", 0)
        if retry_count < 3:
            logger.warning(f"Story validation failed, retrying ({retry_count+1}/3): {state['errors']}")
            return "retry"
        logger.error("Story validation failed after 3 retries")
        return "fail"

    def _build_prompts_node(self, state: StoryState) -> Dict[str, Any]:
        story_dict = state["story_dict"]
        characters = story_dict.get("characters", [])
        for scene in story_dict.get("scenes", []):
            if not scene.get("visual_prompt"):
                scene["visual_prompt"] = build_visual_prompt(scene, characters)
        return {"story_dict": story_dict}

    def _estimate_duration_node(self, state: StoryState) -> Dict[str, Any]:
        story_dict = state["story_dict"]
        scenes = story_dict.get("scenes", [])
        total_ms = estimate_duration(scenes)
        story_dict["total_duration_ms"] = total_ms
        for i, scene in enumerate(scenes):
            words = sum(len(l.get("text", "").split()) for l in scene.get("dialogue", []))
            scene["duration_ms"] = max(words * 70 + 2000, scene.get("duration_ms", 5000))
        return {"story_dict": story_dict}

    def _check_consistency_node(self, state: StoryState) -> Dict[str, Any]:
        passed, issues = check_consistency(state["story_dict"])
        if not passed:
            logger.warning(f"Consistency issues (non-fatal): {issues}")
        return {"validation_passed": passed, "errors": issues}

    def _finalize_node(self, state: StoryState) -> Dict[str, Any]:
        return {"story": state["story_dict"]}

    def run(self, user_prompt: str, style: str = "cinematic") -> Story:
        initial: StoryState = {
            "user_prompt": user_prompt,
            "style": style,
            "raw_story_text": "",
            "story_dict": {},
            "validation_passed": False,
            "retry_count": 0,
            "errors": [],
            "story": None,
        }
        result = self.graph.invoke(initial)
        story_dict = result.get("story") or result.get("story_dict", {})
        if not story_dict:
            raise RuntimeError(f"Story generation failed: {result.get('errors', [])}")
        story_dict["style"] = style
        return Story(**story_dict)
