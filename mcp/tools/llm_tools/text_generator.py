from __future__ import annotations

import json
import os
from typing import Any, Dict

from groq import Groq

from mcp.base_tool import BaseTool, ToolOutput
from shared.constants.constants import GROQ_MODEL_DEFAULT


class TextGeneratorTool(BaseTool):
    name = "text_generator"
    description = "Generate text using Groq LLaMA model"

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        prompt: str = inputs["prompt"]
        system_prompt: str = inputs.get("system_prompt", "You are a helpful assistant.")
        temperature: float = inputs.get("temperature", 0.7)
        max_tokens: int = inputs.get("max_tokens", 4096)
        json_mode: bool = inputs.get("json_mode", False)

        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        kwargs: Dict[str, Any] = {
            "model": os.getenv("GROQ_MODEL", GROQ_MODEL_DEFAULT),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content
        return ToolOutput(success=True, data=text)
