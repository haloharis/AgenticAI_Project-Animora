from __future__ import annotations

import json
import time
from typing import Any, Dict

from mcp.base_tool import BaseTool, ToolOutput
from mcp.tools.llm_tools.text_generator import TextGeneratorTool


class JsonStructurerTool(BaseTool):
    name = "json_structurer"
    description = "Convert raw LLM text into structured JSON matching a schema hint"

    def __init__(self) -> None:
        self._text_gen = TextGeneratorTool()

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        raw_text: str = inputs["raw_text"]
        schema_hint: str = inputs.get("schema_hint", "")

        system_prompt = (
            "You are a JSON conversion assistant. "
            "Convert the given text into a valid JSON object. "
            "Return ONLY the JSON object with no markdown fences or extra text. "
            f"The JSON must match this schema: {schema_hint}"
        )
        prompt = f"Convert this to JSON:\n\n{raw_text}"

        last_exc: Exception | None = None
        for attempt in range(3):
            result = self._text_gen.execute({
                "prompt": prompt,
                "system_prompt": system_prompt,
                "temperature": 0.2,
                "max_tokens": 4096,
                "json_mode": True,
            })
            if not result.success:
                return result
            try:
                parsed = json.loads(result.data)
                return ToolOutput(success=True, data=parsed)
            except json.JSONDecodeError as e:
                last_exc = e
                time.sleep(1)

        return ToolOutput(success=False, error=f"JSON parse failed after 3 attempts: {last_exc}")
