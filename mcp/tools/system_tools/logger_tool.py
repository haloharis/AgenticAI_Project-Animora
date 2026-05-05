from __future__ import annotations

import logging
from typing import Any, Dict

from mcp.base_tool import BaseTool, ToolOutput

logger = logging.getLogger("animora.pipeline")


class LoggerTool(BaseTool):
    name = "logger_tool"
    description = "Structured logging for pipeline events"

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        level: str = inputs.get("level", "info").lower()
        message: str = inputs.get("message", "")
        extra: Dict[str, Any] = inputs.get("extra", {})

        log_fn = getattr(logger, level, logger.info)
        log_fn(f"{message} | {extra}" if extra else message)

        return ToolOutput(success=True, data={"logged": message})
