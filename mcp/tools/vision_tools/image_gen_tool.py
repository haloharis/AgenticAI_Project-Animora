from __future__ import annotations

import os
import time
from typing import Any, Dict

from mcp.base_tool import BaseTool, ToolOutput
from shared.constants.constants import VIDEO_HEIGHT, VIDEO_WIDTH
from shared.utils.helpers import ensure_dirs


class ImageGenTool(BaseTool):
    name = "image_gen"
    description = "Generate images using FLUX.1-schnell via Hugging Face Inference API"

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        prompt: str = inputs["prompt"]
        output_path: str = inputs["output_path"]
        width: int = inputs.get("width", VIDEO_WIDTH)
        height: int = inputs.get("height", VIDEO_HEIGHT)

        ensure_dirs(os.path.dirname(output_path) or ".")

        from huggingface_hub import InferenceClient

        model = os.getenv("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
        token = os.getenv("HF_API_TOKEN")

        client = InferenceClient(token=token)

        for attempt in range(3):
            try:
                image = client.text_to_image(
                    prompt,
                    model=model,
                    width=width,
                    height=height,
                    num_inference_steps=4,
                    guidance_scale=0.0,
                )
                image.save(output_path)
                return ToolOutput(success=True, data={"path": output_path})
            except Exception as e:
                err = str(e)
                if "503" in err or "loading" in err.lower():
                    time.sleep(20 * (attempt + 1))
                    continue
                raise

        return ToolOutput(success=False, error="HF Inference API returned 503 after 3 retries (model loading)")
