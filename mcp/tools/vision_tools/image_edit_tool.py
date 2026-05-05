from __future__ import annotations

import os
from typing import Any, Dict

from PIL import Image, ImageEnhance

from mcp.base_tool import BaseTool, ToolOutput
from shared.utils.helpers import ensure_dirs


class ImageEditTool(BaseTool):
    name = "image_edit"
    description = "Apply basic image transformations using Pillow"

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        image_path: str = inputs["image_path"]
        operation: str = inputs["operation"]
        params: Dict[str, Any] = inputs.get("params", {})
        output_path: str = inputs.get("output_path", image_path)

        ensure_dirs(os.path.dirname(output_path) or ".")
        img = Image.open(image_path)

        if operation == "resize":
            width = params.get("width", img.width)
            height = params.get("height", img.height)
            img = img.resize((width, height), Image.LANCZOS)
        elif operation == "brighten":
            factor = params.get("factor", 1.3)
            img = ImageEnhance.Brightness(img).enhance(factor)
        elif operation == "darken":
            factor = params.get("factor", 0.7)
            img = ImageEnhance.Brightness(img).enhance(factor)
        elif operation == "crop":
            box = (params["left"], params["top"], params["right"], params["bottom"])
            img = img.crop(box)
        elif operation == "contrast":
            factor = params.get("factor", 1.2)
            img = ImageEnhance.Contrast(img).enhance(factor)
        else:
            return ToolOutput(success=False, error=f"Unknown operation: {operation}")

        img.save(output_path)
        return ToolOutput(success=True, data={"path": output_path})
