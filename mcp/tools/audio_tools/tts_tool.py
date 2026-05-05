from __future__ import annotations

import os
from typing import Any, Dict

import requests
from pydub import AudioSegment

from mcp.base_tool import BaseTool, ToolOutput
from shared.constants.constants import DEEPGRAM_TTS_URL
from shared.utils.helpers import ensure_dirs


class TTSTool(BaseTool):
    name = "tts_tool"
    description = "Convert text to speech using Deepgram Aura TTS"

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        text: str = inputs["text"]
        voice: str = inputs.get("voice", os.getenv("DEEPGRAM_TTS_MODEL", "aura-asteria-en"))
        output_path: str = inputs["output_path"]

        ensure_dirs(os.path.dirname(output_path) or ".")

        headers = {
            "Authorization": f"Token {os.getenv('DEEPGRAM_API_KEY')}",
            "Content-Type": "application/json",
            "Accept": "audio/wav",
        }
        params = {
            "model": voice,
            "encoding": "linear16",
            "sample_rate": "44100",
        }
        body = {"text": text}

        response = requests.post(
            DEEPGRAM_TTS_URL,
            headers=headers,
            json=body,
            params=params,
            timeout=60,
        )
        response.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(response.content)

        audio = AudioSegment.from_wav(output_path)
        duration_ms = len(audio)

        return ToolOutput(success=True, data={"path": output_path, "duration_ms": duration_ms})
