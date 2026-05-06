from __future__ import annotations

import io
import os
import urllib.parse
from typing import Any, Dict

import requests
from PIL import Image

from mcp.base_tool import BaseTool, ToolOutput
from shared.constants.constants import VIDEO_HEIGHT, VIDEO_WIDTH
from shared.utils.helpers import ensure_dirs

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"


class ImageGenTool(BaseTool):
    name = "image_gen"
    description = "Generate images using FLUX via Pollinations.ai (free, no API key)"

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        prompt: str = inputs["prompt"]
        output_path: str = inputs["output_path"]
        width: int = inputs.get("width", VIDEO_WIDTH)
        height: int = inputs.get("height", VIDEO_HEIGHT)
        model: str = inputs.get("model", os.getenv("POLLINATIONS_MODEL", "flux"))

        ensure_dirs(os.path.dirname(output_path) or ".")

        encoded_prompt = urllib.parse.quote(prompt)
        url = (
            f"{POLLINATIONS_BASE}/{encoded_prompt}"
            f"?width={width}&height={height}&model={model}&nologo=true"
        )

        resp = requests.get(url, timeout=120)

        if not resp.ok:
            return ToolOutput(
                success=False,
                error=f"Pollinations error {resp.status_code}: {resp.text[:300]}",
            )

        Image.open(io.BytesIO(resp.content)).save(output_path)
        return ToolOutput(success=True, data={"path": output_path})
