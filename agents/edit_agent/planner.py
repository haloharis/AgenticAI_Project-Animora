from __future__ import annotations

import os
from typing import Any, Dict, List

from shared.schemas.pipeline_schema import EditAction, EditIntent, PipelineState
from shared.utils.helpers import get_output_dir, get_temp_dir


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
                scenes = [s for s in story.scenes if s.id == target_scene or str(s.scene_number) == target_scene]

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
            style_modifier = action.parameters.get("style", action.parameters.get("description", ""))
            target_scene = action.target if action.target != "all" else None

            scenes = story.scenes if story else []
            if target_scene and story:
                scenes = [s for s in story.scenes if s.id == target_scene or str(s.scene_number) == target_scene]

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

        elif action.intent == EditIntent.script:
            # Re-run story generation (simplified: just flag for orchestrator)
            calls.append({
                "tool": "logger_tool",
                "inputs": {
                    "level": "info",
                    "message": "Script edit requested — full pipeline re-run required",
                    "extra": {"action": action.model_dump()},
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
