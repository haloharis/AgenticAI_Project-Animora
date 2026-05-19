from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from mcp.tool_executor import ToolExecutor
from mcp.tool_registry import ToolRegistry
from agents.story_agent.planner import build_character_portrait_prompt
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
        log_fn=None,
        progress_fn=None,
    ) -> str:
        temp_dir = get_temp_dir()
        output_dir = get_output_dir()
        images_dir = os.path.join(temp_dir, job_id, "images")
        audio_dir = os.path.join(temp_dir, job_id, "audio")
        job_output_dir = os.path.join(output_dir, job_id)
        ensure_dirs(images_dir, job_output_dir)

        sep = "─" * 60
        style = getattr(story, "style", "")
        total_chars = max(len(story.characters), 1)
        total_scenes = max(len(story.scenes), 1)

        # Step 0: Generate character reference portraits in parallel
        def _gen_portrait(character):
            portrait_path = os.path.join(images_dir, f"ref_{character.id}.png")
            portrait_prompt = build_character_portrait_prompt(character.model_dump(), style)
            print(f"\n{sep}")
            print(f"[VIDEO] Character portrait: \"{character.name}\"  →  PORTRAIT PROMPT:")
            print(portrait_prompt)
            print(sep)
            result = self.executor.run(
                "image_gen",
                {"prompt": portrait_prompt, "output_path": portrait_path},
            )
            return character, portrait_path, result

        with ThreadPoolExecutor(max_workers=min(total_chars, 4)) as pool:
            futures = {pool.submit(_gen_portrait, c): c for c in story.characters}
            for char_idx, future in enumerate(as_completed(futures)):
                character, portrait_path, result = future.result()
                msg = f"Generated reference portrait for character: {character.name}"
                logger.info(msg)
                if log_fn:
                    log_fn(msg)
                if result.success:
                    character.reference_image_path = portrait_path
                else:
                    logger.warning("Portrait generation failed for %s: %s", character.name, result.error)
                if progress_fn:
                    progress_fn(int((char_idx + 1) / total_chars * 15))

        # Step 1: Generate images for each scene in parallel
        def _gen_scene_image(args):
            scene_idx, scene = args
            img_path = os.path.join(images_dir, f"{scene.id}.png")
            print(f"\n{sep}")
            print(f"[VIDEO] Scene {scene.scene_number}: \"{scene.title}\"  →  IMAGE PROMPT:")
            print(scene.visual_prompt)
            print(sep)
            scene_char_ids = {d.character_id for d in scene.dialogue}
            ref_images = [
                c.reference_image_path
                for c in story.characters
                if c.id in scene_char_ids
                and c.reference_image_path
                and os.path.exists(c.reference_image_path)
            ]
            gen_inputs: dict = {"prompt": scene.visual_prompt, "output_path": img_path}
            if ref_images:
                gen_inputs["reference_images"] = ref_images
            result = self.executor.run("image_gen", gen_inputs)
            return scene_idx, scene, img_path, result

        with ThreadPoolExecutor(max_workers=min(total_scenes, 4)) as pool:
            futures = {pool.submit(_gen_scene_image, (i, s)): s for i, s in enumerate(story.scenes)}
            completed = 0
            for future in as_completed(futures):
                scene_idx, scene, img_path, result = future.result()
                msg = f"Generated image for scene: {scene.title}"
                logger.info(msg)
                if log_fn:
                    log_fn(msg)
                if result.success:
                    scene.image_path = img_path
                else:
                    err = f"Image generation failed for scene {scene.id}: {result.error}"
                    logger.error(err)
                    if log_fn:
                        log_fn(err, "error")
                    self._create_placeholder_image(img_path, scene.mood.value)
                    scene.image_path = img_path
                completed += 1
                if progress_fn:
                    progress_fn(15 + int(completed / total_scenes * 65))

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
        if log_fn:
            log_fn("Compositing final video…")
        if progress_fn:
            progress_fn(82)
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
