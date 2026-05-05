from __future__ import annotations

import os
from typing import Any, Dict, List

from mcp.base_tool import BaseTool, ToolOutput
from shared.utils.helpers import ensure_dirs, ms_to_seconds


def _ms_to_srt_time(ms: int) -> str:
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    ms_rem = ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms_rem:03d}"


class SubtitleTool(BaseTool):
    name = "subtitle"
    description = "Add subtitles to video using MoviePy"

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        video_path: str = inputs["video_path"]
        scenes: List[Dict[str, Any]] = inputs.get("scenes", [])
        output_path: str = inputs["output_path"]
        scene_timings: Dict[str, Dict[str, int]] = inputs.get("scene_timings", {})

        ensure_dirs(os.path.dirname(output_path) or ".")

        import imageio_ffmpeg
        os.environ.setdefault("IMAGEIO_FFMPEG_EXE", imageio_ffmpeg.get_ffmpeg_exe())

        from moviepy import CompositeVideoClip, TextClip, VideoFileClip

        video = VideoFileClip(video_path)
        subtitle_clips = []

        for scene in scenes:
            scene_id = scene.get("id", "")
            timings = scene_timings.get(scene_id, {})
            start_ms = timings.get("start_ms", 0)
            dialogue = scene.get("dialogue", [])

            offset_ms = 0
            for line in dialogue:
                text = line.get("text", "")
                dur_ms = line.get("duration_estimate_ms", 2000)
                line_start = ms_to_seconds(start_ms + offset_ms)
                line_dur = ms_to_seconds(dur_ms)

                try:
                    txt_clip = (
                        TextClip(text=text, font_size=28, color="white", bg_color="black", method="caption", size=(video.w, None))
                        .with_start(line_start)
                        .with_duration(line_dur)
                        .with_position(("center", "bottom"))
                    )
                    subtitle_clips.append(txt_clip)
                except Exception:
                    pass

                offset_ms += dur_ms

        if subtitle_clips:
            final = CompositeVideoClip([video, *subtitle_clips])
        else:
            final = video

        final.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", logger=None)
        video.close()

        return ToolOutput(success=True, data={"path": output_path})
