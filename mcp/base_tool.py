from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ToolOutput(BaseModel):
    success: bool
    data: Any = None
    error: Optional[str] = None


class BaseTool(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        ...

    def safe_execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        try:
            return self.execute(inputs)
        except Exception as e:
            logger.exception(f"[{self.name}] execution error: {e}")
            return ToolOutput(success=False, error=str(e))
