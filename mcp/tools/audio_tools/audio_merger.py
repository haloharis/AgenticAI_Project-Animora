from __future__ import annotations

import os
from typing import Any, Dict, List

from pydub import AudioSegment

from mcp.base_tool import BaseTool, ToolOutput
from shared.utils.helpers import ensure_dirs


class AudioMergerTool(BaseTool):
    name = "audio_merger"
    description = "Merge dialogue audio files with background music"

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        dialogue_files: List[str] = inputs["dialogue_files"]
        bgm_file: str = inputs["bgm_file"]
        output_path: str = inputs["output_path"]
        bgm_volume_db: float = inputs.get("bgm_volume_db", -12.0)

        ensure_dirs(os.path.dirname(output_path) or ".")

        if dialogue_files:
            combined = AudioSegment.empty()
            for f in dialogue_files:
                combined += AudioSegment.from_wav(f)
        else:
            combined = AudioSegment.silent(duration=5000)

        bgm = AudioSegment.from_wav(bgm_file) + bgm_volume_db
        # Loop BGM to match or exceed dialogue length
        if len(bgm) < len(combined):
            loops = (len(combined) // len(bgm)) + 1
            bgm = bgm * loops
        bgm = bgm[: len(combined)]

        merged = combined.overlay(bgm)
        merged.export(output_path, format="wav")

        return ToolOutput(success=True, data={"path": output_path, "duration_ms": len(merged)})
