from __future__ import annotations

import math
import os
from typing import Any, Dict, List

import numpy as np
from PIL import Image

from mcp.base_tool import BaseTool, ToolOutput
from shared.constants.constants import (
    KEN_BURNS_PRESETS,
    KEN_BURNS_SAFETY,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
)
from shared.utils.helpers import ensure_dirs, ms_to_seconds


_CROSSFADE_DURATION = 0.5  # seconds for true cross-dissolve between scenes


def _ease_in_out(t: float) -> float:
    """Smooth cosine ease-in-out; t must be in [0, 1]."""
    return 0.5 - math.cos(math.pi * t) / 2.0


def _apply_ken_burns(
    clip,
    zoom_start: float,
    zoom_end: float,
    pan_x: int,
    pan_y: int,
    target_w: int,
    target_h: int,
):
    """
    Ken Burns pan/zoom with smooth easing and no per-frame upscale jitter.

    The source image is pre-scaled ONCE to provide zoom + pan headroom.
    Per-frame we only CROP + DOWNSCALE, eliminating the integer-rounding
    jitter that caused the 'earthquake' effect when upscaling each frame.
    """
    dur = clip.duration
    max_zoom = max(zoom_start, zoom_end)

    src_w = int(target_w * max_zoom * KEN_BURNS_SAFETY)
    src_h = int(target_h * max_zoom * KEN_BURNS_SAFETY)
    src_w += src_w % 2  # keep even for codec compatibility
    src_h += src_h % 2

    raw = clip.get_frame(0)
    src_arr = np.array(
        Image.fromarray(raw.astype("uint8")).resize((src_w, src_h), Image.BICUBIC)
    )

    # Pre-render all frames into a lookup array to avoid repeated PIL calls at playback time.
    n_frames = max(1, int(math.ceil(dur * VIDEO_FPS)))
    rendered: list = [None] * n_frames
    for fi in range(n_frames):
        t = fi / VIDEO_FPS
        p = _ease_in_out(t / dur if dur > 0 else 0.0)
        zoom = zoom_start + (zoom_end - zoom_start) * p
        win_w = min(int(src_w / zoom), src_w)
        win_h = min(int(src_h / zoom), src_h)
        cx = src_w // 2 + int(pan_x * p)
        cy = src_h // 2 + int(pan_y * p)
        x1 = max(0, min(cx - win_w // 2, src_w - win_w))
        y1 = max(0, min(cy - win_h // 2, src_h - win_h))
        cropped = src_arr[y1 : y1 + win_h, x1 : x1 + win_w]
        rendered[fi] = np.array(Image.fromarray(cropped).resize((target_w, target_h), Image.BICUBIC))

    def zoom_frame(get_frame, t):
        fi = min(int(t * VIDEO_FPS), n_frames - 1)
        return rendered[fi]

    return clip.transform(zoom_frame)


def _make_dissolve(clip_a, clip_b, dur: float, fps: int):
    """True cross-dissolve: linearly blend the last `dur` s of A with the first `dur` s of B."""
    from moviepy import VideoClip

    def make_frame(t):
        alpha = t / dur
        fa = clip_a.get_frame(clip_a.duration - dur + t)
        fb = clip_b.get_frame(t)
        return (fa * (1.0 - alpha) + fb * alpha).astype("uint8")

    trans = VideoClip(make_frame, duration=dur).with_fps(fps)
    if clip_b.audio is not None:
        trans = trans.with_audio(clip_b.audio.subclipped(0, min(dur, clip_b.audio.duration)))
    return trans


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
        for scene in scenes:
            image_path: str = scene["image_path"]
            audio_path: str = scene["audio_path"]
            duration_ms: int = scene["duration_ms"]
            scene_number: int = scene.get("scene_number", 0)

            duration_s = max(ms_to_seconds(duration_ms), 1.0)
            preset = KEN_BURNS_PRESETS[scene_number % len(KEN_BURNS_PRESETS)]

            img_clip = ImageClip(image_path).with_duration(duration_s)
            img_clip = _apply_ken_burns(
                img_clip,
                preset["zoom_start"],
                preset["zoom_end"],
                preset["pan_x"],
                preset["pan_y"],
                VIDEO_WIDTH,
                VIDEO_HEIGHT,
            )

            if os.path.exists(audio_path):
                audio_clip = AudioFileClip(audio_path)
                audio_clip = audio_clip.subclipped(0, min(audio_clip.duration, duration_s))
                img_clip = img_clip.with_audio(audio_clip)

            clips.append(img_clip)

        if not clips:
            return ToolOutput(success=False, error="No scenes to compose")

        # Build final sequence; fade/dissolve transitions use true cross-dissolve frame-blending.
        # next_start tracks how many seconds of the next clip are consumed by the dissolve.
        parts: List = []
        next_start: Dict[int, float] = {}

        for i, clip in enumerate(clips):
            transition = scenes[i].get("transition", "cut")
            t_start = next_start.get(i, 0.0)

            if i == len(clips) - 1:
                parts.append(clip.subclipped(t_start) if t_start > 0 else clip)
            elif transition in ("fade", "dissolve"):
                body_end = clip.duration - _CROSSFADE_DURATION
                if body_end > t_start + 0.1:
                    parts.append(clip.subclipped(t_start, body_end))
                parts.append(_make_dissolve(clip, clips[i + 1], _CROSSFADE_DURATION, VIDEO_FPS))
                next_start[i + 1] = _CROSSFADE_DURATION
            else:
                parts.append(clip.subclipped(t_start) if t_start > 0 else clip)

        final = concatenate_videoclips(parts, method="compose")
        import multiprocessing
        n_threads = max(2, multiprocessing.cpu_count() - 1)
        final.write_videofile(
            output_path,
            fps=VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=output_path + ".temp_audio.m4a",
            remove_temp=True,
            threads=n_threads,
            logger=None,
        )
        final.close()

        return ToolOutput(success=True, data={"path": output_path})
