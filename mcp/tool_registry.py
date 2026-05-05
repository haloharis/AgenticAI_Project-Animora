from __future__ import annotations

import logging
from typing import Dict, List

from mcp.base_tool import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    _tools: Dict[str, BaseTool] = {}

    @classmethod
    def register(cls, tool: BaseTool) -> None:
        cls._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    @classmethod
    def get(cls, name: str) -> BaseTool:
        if name not in cls._tools:
            raise KeyError(f"Tool '{name}' not registered. Available: {list(cls._tools.keys())}")
        return cls._tools[name]

    @classmethod
    def list_tools(cls) -> List[str]:
        return list(cls._tools.keys())

    @classmethod
    def auto_register_all(cls) -> None:
        from mcp.tools.llm_tools.text_generator import TextGeneratorTool
        from mcp.tools.llm_tools.json_structurer import JsonStructurerTool
        from mcp.tools.audio_tools.tts_tool import TTSTool
        from mcp.tools.audio_tools.bgm_tool import BGMTool
        from mcp.tools.audio_tools.audio_merger import AudioMergerTool
        from mcp.tools.vision_tools.image_gen_tool import ImageGenTool
        from mcp.tools.vision_tools.image_edit_tool import ImageEditTool
        from mcp.tools.vision_tools.style_transfer import StyleTransferTool
        from mcp.tools.video_tools.compositor_tool import CompositorTool
        from mcp.tools.video_tools.ffmpeg_tool import FFmpegTool
        from mcp.tools.video_tools.subtitle_tool import SubtitleTool
        from mcp.tools.system_tools.file_tool import FileTool
        from mcp.tools.system_tools.state_tool import StateTool
        from mcp.tools.system_tools.logger_tool import LoggerTool

        tools = [
            TextGeneratorTool(), JsonStructurerTool(),
            TTSTool(), BGMTool(), AudioMergerTool(),
            ImageGenTool(), ImageEditTool(), StyleTransferTool(),
            CompositorTool(), FFmpegTool(), SubtitleTool(),
            FileTool(), StateTool(), LoggerTool(),
        ]
        for tool in tools:
            cls.register(tool)
        logger.info(f"Auto-registered {len(tools)} tools")
