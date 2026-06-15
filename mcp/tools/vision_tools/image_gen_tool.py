from __future__ import annotations

import base64
import os
import time
from typing import Any, Dict, List, Optional

import requests

from mcp.base_tool import BaseTool, ToolOutput
from shared.constants.constants import ARK_API_URL_DEFAULT, ARK_MODEL_DEFAULT, VIDEO_HEIGHT, VIDEO_WIDTH
from shared.utils.helpers import ensure_dirs


class ImageGenTool(BaseTool):
    name = "image_gen"
    description = "Generate images using Seedream via ARK API (ByteDance)"

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        prompt: str = inputs["prompt"]
        output_path: str = inputs["output_path"]
        width: int = inputs.get("width", VIDEO_WIDTH)
        height: int = inputs.get("height", VIDEO_HEIGHT)
        reference_images: Optional[List[str]] = inputs.get("reference_images")

        ensure_dirs(os.path.dirname(output_path) or ".")

        api_key = os.getenv("ARK_API_KEY")
        api_url = os.getenv("ARK_API_URL", ARK_API_URL_DEFAULT)
        model = os.getenv("ARK_MODEL", ARK_MODEL_DEFAULT)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": f"{width}x{height}",
            "response_format": "b64_json",
        }

        # Encode reference portraits as IP embeddings (subject_reference)
        if reference_images:
            encoded_refs = []
            for ref_path in reference_images:
                try:
                    with open(ref_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    encoded_refs.append({"type": "image", "url": f"data:image/png;base64,{b64}"})
                except OSError:
                    pass
            if encoded_refs:
                payload["subject_reference"] = encoded_refs

        for attempt in range(3):
            try:
                resp = requests.post(api_url, headers=headers, json=payload, timeout=120)
                if resp.status_code == 200:
                    data = resp.json()
                    b64_image = data["data"][0]["b64_json"]
                    image_bytes = base64.b64decode(b64_image)
                    with open(output_path, "wb") as f:
                        f.write(image_bytes)
                    return ToolOutput(success=True, data={"path": output_path})
                if resp.status_code in (503, 429):
                    time.sleep(20 * (attempt + 1))
                    continue
                # If subject_reference caused a 400, retry without it
                if resp.status_code == 400 and "subject_reference" in payload:
                    payload.pop("subject_reference")
                    continue
                resp.raise_for_status()
            except requests.exceptions.Timeout:
                if attempt < 2:
                    time.sleep(20 * (attempt + 1))
                    continue
                raise

        return ToolOutput(
            success=False,
            error="ARK Seedream API returned error after 3 retries",
        )
