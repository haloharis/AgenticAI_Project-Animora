from __future__ import annotations

import os
from typing import Any, Dict

import numpy as np
from pydub import AudioSegment

from mcp.base_tool import BaseTool, ToolOutput
from shared.constants.constants import MOOD_BGM_FREQ
from shared.utils.helpers import ensure_dirs


class BGMTool(BaseTool):
    name = "bgm_tool"
    description = "Generate ambient background music using sine wave synthesis"

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        mood: str = inputs.get("mood", "calm")
        duration_ms: int = inputs["duration_ms"]
        output_path: str = inputs["output_path"]

        ensure_dirs(os.path.dirname(output_path) or ".")

        freq = MOOD_BGM_FREQ.get(mood, 432)
        sample_rate = 44100
        num_samples = int(sample_rate * duration_ms / 1000)
        t = np.linspace(0, duration_ms / 1000, num_samples, dtype=np.float32)

        # Three harmonics for a richer ambient sound
        wave = (
            np.sin(2 * np.pi * freq * t) * 0.3
            + np.sin(2 * np.pi * freq * 1.5 * t) * 0.15
            + np.sin(2 * np.pi * freq * 2.0 * t) * 0.10
        )
        pcm = (wave * 32767).astype(np.int16)

        audio = AudioSegment(
            pcm.tobytes(),
            frame_rate=sample_rate,
            sample_width=2,
            channels=1,
        )
        audio = audio.fade_in(500).fade_out(800)
        audio.export(output_path, format="wav")

        return ToolOutput(success=True, data={"path": output_path, "duration_ms": len(audio)})
