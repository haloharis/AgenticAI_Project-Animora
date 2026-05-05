from __future__ import annotations

import os
import subprocess
from typing import Any, Dict

from mcp.base_tool import BaseTool, ToolOutput


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


class FFmpegTool(BaseTool):
    name = "ffmpeg"
    description = "Run FFmpeg operations: compress, get_info, extract_audio"

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        operation: str = inputs["operation"]
        input_path: str = inputs.get("input_path", "")
        output_path: str = inputs.get("output_path", "")
        params: Dict[str, Any] = inputs.get("params", {})

        ffmpeg = _get_ffmpeg()

        if operation == "get_info":
            result = subprocess.run(
                [ffmpeg, "-i", input_path],
                capture_output=True,
                text=True,
            )
            return ToolOutput(success=True, data={"info": result.stderr})

        elif operation == "compress":
            crf = params.get("crf", 28)
            cmd = [ffmpeg, "-i", input_path, "-crf", str(crf), "-y", output_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return ToolOutput(success=False, error=result.stderr)
            return ToolOutput(success=True, data={"path": output_path})

        elif operation == "extract_audio":
            cmd = [ffmpeg, "-i", input_path, "-vn", "-acodec", "pcm_s16le", "-y", output_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return ToolOutput(success=False, error=result.stderr)
            return ToolOutput(success=True, data={"path": output_path})

        return ToolOutput(success=False, error=f"Unknown operation: {operation}")
