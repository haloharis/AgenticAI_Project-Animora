from __future__ import annotations

import logging
import os
from typing import Optional

from mcp.tool_executor import ToolExecutor
from mcp.tool_registry import ToolRegistry
from shared.schemas.pipeline_schema import AudioSegment, Story, TimingManifest
from shared.utils.helpers import get_temp_dir, save_json

logger = logging.getLogger(__name__)

VOICE_FALLBACK = {
    "aura-asteria-en": "aura-asteria-en",
    "aura-orion-en": "aura-orion-en",
    "aura-luna-en": "aura-luna-en",
    "aura-arcas-en": "aura-arcas-en",
}


def _find_character(story: Story, character_id: str):
    for c in story.characters:
        if c.id == character_id:
            return c
    return story.characters[0] if story.characters else None


class AudioAgent:
    def __init__(self) -> None:
        self.executor = ToolExecutor(ToolRegistry)

    def run(self, story: Story, job_id: str, log_fn=None) -> TimingManifest:
        temp_dir = get_temp_dir()
        audio_dir = os.path.join(temp_dir, job_id, "audio")
        os.makedirs(audio_dir, exist_ok=True)

        segments: list[AudioSegment] = []
        scene_timings: dict[str, dict] = {}
        current_ms = 0

        sep = "─" * 60
        for scene in story.scenes:
            scene_start = current_ms
            dialogue_files: list[str] = []
            msg = f"Generating audio for scene: {scene.title}"
            logger.info(msg)
            if log_fn:
                log_fn(msg)
            print(f"\n{sep}")
            print(f"[AUDIO] Scene {scene.scene_number}: \"{scene.title}\"  (mood: {scene.mood.value})")

            for i, line in enumerate(scene.dialogue):
                char = _find_character(story, line.character_id)
                voice = char.voice_id if char else "aura-asteria-en"
                out_path = os.path.join(audio_dir, f"{scene.id}_line_{i}.wav")
                print(f"  TTS [{i+1}] ({line.character_id}, voice={voice}): {line.text}")

                result = self.executor.run(
                    "tts_tool",
                    {"text": line.text, "voice": voice, "output_path": out_path},
                )
                if result.success:
                    dur_ms = result.data["duration_ms"]
                    line.duration_estimate_ms = dur_ms
                    dialogue_files.append(out_path)
                    segments.append(
                        AudioSegment(
                            scene_id=scene.id,
                            character_id=char.id if char else None,
                            text=line.text,
                            audio_file=out_path,
                            segment_type="dialogue",
                            duration_ms=dur_ms,
                        )
                    )
                    current_ms += dur_ms
                else:
                    warn = f"TTS failed for line {i} in scene {scene.id}: {result.error}"
                    logger.warning(warn)
                    if log_fn:
                        log_fn(warn, "warning")

            # Calculate scene duration from actual dialogue
            scene_dialogue_ms = sum(l.duration_estimate_ms for l in scene.dialogue)
            scene_duration = max(scene_dialogue_ms, scene.duration_ms, 3000)

            # Generate BGM
            if log_fn:
                log_fn(f"Generating BGM for scene: {scene.title}")
            bgm_path = os.path.join(audio_dir, f"{scene.id}_bgm.wav")
            bgm_result = self.executor.run(
                "bgm_tool",
                {"mood": scene.mood.value, "duration_ms": scene_duration, "output_path": bgm_path},
            )

            # Merge dialogue + BGM
            merged_path = os.path.join(audio_dir, f"{scene.id}_merged.wav")
            if dialogue_files and bgm_result.success:
                self.executor.run(
                    "audio_merger",
                    {
                        "dialogue_files": dialogue_files,
                        "bgm_file": bgm_path,
                        "output_path": merged_path,
                        "bgm_volume_db": -6.0,
                        "target_duration_ms": scene_duration,
                    },
                )
            elif bgm_result.success:
                merged_path = bgm_path
            elif dialogue_files:
                # No BGM — concatenate dialogue and pad to scene_duration
                from pydub import AudioSegment as PydubSeg
                combined = PydubSeg.empty()
                for f in dialogue_files:
                    combined += PydubSeg.from_wav(f)
                if len(combined) < scene_duration:
                    combined = combined + PydubSeg.silent(duration=scene_duration - len(combined))
                combined.export(merged_path, format="wav")

            scene.duration_ms = scene_duration
            scene_end = scene_start + scene_duration
            scene_timings[scene.id] = {"start_ms": scene_start, "end_ms": scene_end}
            current_ms = scene_end

        story.total_duration_ms = current_ms

        manifest = TimingManifest(
            job_id=job_id,
            segments=segments,
            scene_timings=scene_timings,
        )

        manifest_path = os.path.join(get_temp_dir(), job_id, "timing_manifest.json")
        save_json(manifest.model_dump(mode="json"), manifest_path)

        return manifest
