from __future__ import annotations

from typing import Any, Dict

from mcp.base_tool import BaseTool, ToolOutput
from mcp.tools.vision_tools.image_gen_tool import ImageGenTool


class StyleTransferTool(BaseTool):
    name = "style_transfer"
    description = "Re-generate image with a different visual style using Stable Diffusion XL"

    def __init__(self) -> None:
        self._image_gen = ImageGenTool()

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        original_prompt: str = inputs["original_prompt"]
        style: str = inputs["style"]
        output_path: str = inputs["output_path"]

        enhanced_prompt = f"{original_prompt}, {style} style, high quality"

        return self._image_gen.execute({
            "prompt": enhanced_prompt,
            "output_path": output_path,
        })
