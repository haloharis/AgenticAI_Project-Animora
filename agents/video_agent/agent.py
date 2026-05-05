from __future__ import annotations

import logging
import os

from mcp.tool_executor import ToolExecutor
from mcp.tool_registry import ToolRegistry
from shared.schemas.pipeline_schema import Story, TimingManifest
from shared.utils.helpers import ensure_dirs, get_output_dir, get_temp_dir

logger = logging.getLogger(__name__)


class VideoAgent:
    def __init__(self) -> None:
        self.executor = ToolExecutor(ToolRegistry)

    def run(
        self,
        story: Story,
        manifest: TimingManifest,
        job_id: str,
        add_subtitles: bool = False,
    ) -> str:
        temp_dir = get_temp_dir()
        output_dir = get_output_dir()
        images_dir = os.path.join(temp_dir, job_id, "images")
        audio_dir = os.path.join(temp_dir, job_id, "audio")
        job_output_dir = os.path.join(output_dir, job_id)
        ensure_dirs(images_dir, job_output_dir)

        # Step 1: Generate images for each scene
        for scene in story.scenes:
            img_path = os.path.join(images_dir, f"{scene.id}.png")
            logger.info(f"Generating image for scene: {scene.title}")
            result = self.executor.run(
                "image_gen",
                {"prompt": scene.visual_prompt, "output_path": img_path},
            )
            if result.success:
                scene.image_path = img_path
            else:
                logger.error(f"Image generation failed for scene {scene.id}: {result.error}")
                # Create a placeholder colored image
                self._create_placeholder_image(img_path, scene.mood.value)
                scene.image_path = img_path

        # Step 2: Build scene payloads for compositor
        scene_payloads = []
        for scene in story.scenes:
            merged_audio = os.path.join(audio_dir, f"{scene.id}_merged.wav")
            if not os.path.exists(merged_audio):
                merged_audio = os.path.join(audio_dir, f"{scene.id}_bgm.wav")

            scene_payloads.append({
                "image_path": scene.image_path,
                "audio_path": merged_audio,
                "duration_ms": scene.duration_ms,
                "transition": scene.transition.value,
                "scene_number": scene.scene_number,
                "id": scene.id,
                "dialogue": [d.model_dump() for d in scene.dialogue],
            })

        # Step 3: Composite
        output_path = os.path.join(job_output_dir, "final_output.mp4")
        logger.info("Compositing final video...")
        comp_result = self.executor.run(
            "compositor",
            {"scenes": scene_payloads, "output_path": output_path},
        )
        if not comp_result.success:
            raise RuntimeError(f"Video composition failed: {comp_result.error}")

        # Step 4: Optional subtitles
        if add_subtitles:
            sub_path = output_path.replace(".mp4", "_subtitled.mp4")
            sub_result = self.executor.run(
                "subtitle",
                {
                    "video_path": output_path,
                    "scenes": scene_payloads,
                    "output_path": sub_path,
                    "scene_timings": manifest.scene_timings,
                },
            )
            if sub_result.success:
                output_path = sub_path

        return output_path

    def _create_placeholder_image(self, path: str, mood: str) -> None:
        from PIL import Image
        mood_colors = {
            "happy": (255, 220, 100),
            "sad": (100, 130, 180),
            "tense": (180, 60, 60),
            "calm": (100, 180, 150),
            "mysterious": (80, 60, 120),
            "epic": (180, 120, 40),
            "romantic": (200, 120, 150),
        }
        color = mood_colors.get(mood, (128, 128, 128))
        img = Image.new("RGB", (1280, 720), color)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.save(path)
