from __future__ import annotations

import os
from typing import Any, Dict, List

import numpy as np
from PIL import Image

from mcp.base_tool import BaseTool, ToolOutput
from shared.constants.constants import KEN_BURNS_PRESETS, VIDEO_FPS, VIDEO_HEIGHT, VIDEO_WIDTH
from shared.utils.helpers import ensure_dirs, ms_to_seconds


_FADE_DURATION = 0.4  # seconds for fade in/out between scenes


def _apply_ken_burns(
    clip, zoom_start: float, zoom_end: float,
    pan_x: int, pan_y: int,
    target_w: int, target_h: int,
):
    dur = clip.duration

    def zoom_frame(get_frame, t):
        frame = get_frame(t)
        progress = t / dur if dur > 0 else 0
        zoom = zoom_start + (zoom_end - zoom_start) * progress
        h, w = frame.shape[:2]
        new_w = max(target_w, int(w * zoom))
        new_h = max(target_h, int(h * zoom))
        img = Image.fromarray(frame.astype("uint8"))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        # Pan drifts linearly from 0 to pan_x/pan_y over the clip duration
        x1 = (new_w - target_w) // 2 + int(pan_x * progress)
        y1 = (new_h - target_h) // 2 + int(pan_y * progress)
        x1 = max(0, min(x1, new_w - target_w))
        y1 = max(0, min(y1, new_h - target_h))
        img = img.crop((x1, y1, x1 + target_w, y1 + target_h))
        return np.array(img)

    return clip.transform(zoom_frame)


def _apply_fadein(clip):
    dur = _FADE_DURATION

    def fade_frame(get_frame, t):
        frame = get_frame(t)
        alpha = min(t / dur, 1.0)
        return (frame * alpha).astype("uint8")

    return clip.transform(fade_frame)


def _apply_fadeout(clip):
    total = clip.duration
    dur = _FADE_DURATION

    def fade_frame(get_frame, t):
        frame = get_frame(t)
        alpha = min((total - t) / dur, 1.0)
        return (frame * alpha).astype("uint8")

    return clip.transform(fade_frame)


class CompositorTool(BaseTool):
    name = "compositor"
    description = "Compose scenes into final MP4 using MoviePy with Ken Burns animation"

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        scenes: List[Dict[str, Any]] = inputs["scenes"]
        output_path: str = inputs["output_path"]

        ensure_dirs(os.path.dirname(output_path) or ".")

        import imageio_ffmpeg
        os.environ.setdefault("IMAGEIO_FFMPEG_EXE", imageio_ffmpeg.get_ffmpeg_exe())

        from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

        clips = []
        for i, scene in enumerate(scenes):
            image_path: str = scene["image_path"]
            audio_path: str = scene["audio_path"]
            duration_ms: int = scene["duration_ms"]
            scene_number: int = scene.get("scene_number", 0)
            transition: str = scene.get("transition", "cut")

            duration_s = max(ms_to_seconds(duration_ms), 1.0)
            preset = KEN_BURNS_PRESETS[scene_number % len(KEN_BURNS_PRESETS)]

            img_clip = ImageClip(image_path).with_duration(duration_s)
            img_clip = _apply_ken_burns(
                img_clip,
                preset["zoom_start"], preset["zoom_end"],
                preset["pan_x"], preset["pan_y"],
                VIDEO_WIDTH, VIDEO_HEIGHT,
            )

            if os.path.exists(audio_path):
                audio_clip = AudioFileClip(audio_path)
                audio_clip = audio_clip.subclipped(0, min(audio_clip.duration, duration_s))
                img_clip = img_clip.with_audio(audio_clip)

            # Apply fade transitions: fade in this clip and fade out the previous one
            if i > 0 and transition in ("fade", "dissolve"):
                img_clip = _apply_fadein(img_clip)
                clips[-1] = _apply_fadeout(clips[-1])

            clips.append(img_clip)

        if not clips:
            return ToolOutput(success=False, error="No scenes to compose")

        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(
            output_path,
            fps=VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=output_path + ".temp_audio.m4a",
            remove_temp=True,
            logger=None,
        )
        final.close()

        return ToolOutput(success=True, data={"path": output_path})
