from __future__ import annotations

import os
import re
from typing import Any, Dict, List

from shared.schemas.pipeline_schema import EditAction, EditIntent, PipelineState, Scene
from shared.utils.helpers import get_output_dir, get_temp_dir


def _scene_matches_target(scene: Scene, target: str) -> bool:
    """Match a scene against a target string like 'all', 'scene_3', '3', or a UUID id."""
    if scene.id == target:
        return True
    if str(scene.scene_number) == target:
        return True
    # Handle "scene_3", "scene3", "scene_003" — extract the numeric part and compare
    m = re.search(r"\d+", target)
    if m and str(scene.scene_number) == str(int(m.group())):
        return True
    return False


class EditPlanner:
    def plan(self, action: EditAction, pipeline_state: PipelineState) -> List[Dict[str, Any]]:
        job_id = pipeline_state.job_id
        temp_dir = get_temp_dir()
        output_dir = get_output_dir()
        audio_dir = os.path.join(temp_dir, job_id, "audio")
        images_dir = os.path.join(temp_dir, job_id, "images")
        final_video = os.path.join(output_dir, job_id, "final_output.mp4")

        calls: List[Dict[str, Any]] = []
        story = pipeline_state.story

        if action.intent == EditIntent.audio:
            mood = action.parameters.get("mood", "calm")
            target_scene = action.target if action.target != "all" else None

            scenes = story.scenes if story else []
            if target_scene and story:
                scenes = [s for s in story.scenes if _scene_matches_target(s, target_scene)]

            for scene in scenes:
                bgm_path = os.path.join(audio_dir, f"{scene.id}_bgm.wav")
                merged_path = os.path.join(audio_dir, f"{scene.id}_merged.wav")
                calls.append({
                    "tool": "bgm_tool",
                    "inputs": {"mood": mood, "duration_ms": scene.duration_ms, "output_path": bgm_path},
                })

                dialogue_files = [
                    os.path.join(audio_dir, f"{scene.id}_line_{i}.wav")
                    for i in range(len(scene.dialogue))
                    if os.path.exists(os.path.join(audio_dir, f"{scene.id}_line_{i}.wav"))
                ]
                if dialogue_files:
                    calls.append({
                        "tool": "audio_merger",
                        "inputs": {
                            "dialogue_files": dialogue_files,
                            "bgm_file": bgm_path,
                            "output_path": merged_path,
                        },
                    })

            # Recomposite
            if story:
                calls.append(self._compositor_call(story, audio_dir, images_dir, final_video))

        elif action.intent == EditIntent.video_frame:
            # Try well-known keys first, then fall back to any string value in parameters,
            # then fall back to the raw user query so the edit is never silently dropped.
            style_modifier = (
                action.parameters.get("style")
                or action.parameters.get("description")
                or next((str(v) for v in action.parameters.values() if v), None)
                or action.query
            )
            target_scene = action.target if action.target != "all" else None

            scenes = story.scenes if story else []
            if target_scene and story:
                scenes = [s for s in story.scenes if _scene_matches_target(s, target_scene)]

            for scene in scenes:
                img_path = os.path.join(images_dir, f"{scene.id}.png")
                new_prompt = scene.visual_prompt
                if style_modifier:
                    new_prompt = f"{new_prompt}, {style_modifier}"
                calls.append({
                    "tool": "image_gen",
                    "inputs": {"prompt": new_prompt, "output_path": img_path},
                })

            if story:
                calls.append(self._compositor_call(story, audio_dir, images_dir, final_video))

        elif action.intent == EditIntent.video:
            if story:
                subtitle = action.parameters.get("subtitles", False)
                calls.append(self._compositor_call(story, audio_dir, images_dir, final_video))
                if subtitle:
                    sub_path = final_video.replace(".mp4", "_subtitled.mp4")
                    calls.append({
                        "tool": "subtitle",
                        "inputs": {
                            "video_path": final_video,
                            "scenes": [s.model_dump() for s in story.scenes],
                            "output_path": sub_path,
                        },
                    })
                    # Tell executor to update pipeline_state.final_video_path to the subtitled file.
                    calls.append({
                        "tool": "__update_final_video__",
                        "inputs": {"new_path": sub_path},
                    })

        elif action.intent == EditIntent.script:
            # Signal the executor to re-run story → audio → video with the edit instruction.
            calls.append({
                "tool": "__story_rerun__",
                "inputs": {
                    "edit_instruction": action.query,
                    "original_prompt": pipeline_state.user_prompt,
                    "style": pipeline_state.style,
                    "job_id": job_id,
                },
            })

        return calls

    def _compositor_call(self, story, audio_dir: str, images_dir: str, output_path: str) -> Dict[str, Any]:
        scene_payloads = []
        for scene in story.scenes:
            merged = os.path.join(audio_dir, f"{scene.id}_merged.wav")
            if not os.path.exists(merged):
                merged = os.path.join(audio_dir, f"{scene.id}_bgm.wav")
            scene_payloads.append({
                "image_path": scene.image_path or os.path.join(images_dir, f"{scene.id}.png"),
                "audio_path": merged,
                "duration_ms": scene.duration_ms,
                "transition": scene.transition.value,
                "scene_number": scene.scene_number,
            })
        return {"tool": "compositor", "inputs": {"scenes": scene_payloads, "output_path": output_path}}
