from __future__ import annotations

import os
import time
from typing import Any, Dict

import requests

from mcp.base_tool import BaseTool, ToolOutput
from shared.constants.constants import VIDEO_HEIGHT, VIDEO_WIDTH
from shared.utils.helpers import ensure_dirs

_CF_URL = (
    "https://api.cloudflare.com/client/v4/accounts/{account_id}"
    "/ai/run/@cf/stabilityai/stable-diffusion-xl-base-1.0"
)


def _round64(n: int) -> int:
    """Snap n down to the nearest multiple of 64 (SDXL latent-space requirement)."""
    return max(64, (n // 64) * 64)


class ImageGenTool(BaseTool):
    name = "image_gen"
    description = "Generate images using Stable Diffusion XL via Cloudflare Workers AI"

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        prompt: str = inputs["prompt"]
        output_path: str = inputs["output_path"]
        width: int = _round64(inputs.get("width", VIDEO_WIDTH))
        height: int = _round64(inputs.get("height", VIDEO_HEIGHT))

        ensure_dirs(os.path.dirname(output_path) or ".")

        token = os.getenv("CF_API_TOKEN")
        account_id = os.getenv("CF_ACCOUNT_ID")
        url = _CF_URL.format(account_id=account_id)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        negative_prompt = (
            "ugly, blurry, low quality, bad anatomy, extra limbs, deformed, "
            "watermark, text, logo, out of frame, duplicate, extra characters, "
            "poorly drawn, disfigured, mutated, oversaturated, noisy"
        )
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "num_steps": 20,
            "guidance": 7.5,
            "width": width,
            "height": height,
        }

        for attempt in range(3):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=120)
                if resp.status_code == 200:
                    with open(output_path, "wb") as f:
                        f.write(resp.content)
                    return ToolOutput(success=True, data={"path": output_path})
                if resp.status_code in (503, 429):
                    time.sleep(20 * (attempt + 1))
                    continue
                resp.raise_for_status()
            except requests.exceptions.Timeout:
                if attempt < 2:
                    time.sleep(20 * (attempt + 1))
                    continue
                raise

        return ToolOutput(
            success=False,
            error="Cloudflare Workers AI returned error after 3 retries",
        )
