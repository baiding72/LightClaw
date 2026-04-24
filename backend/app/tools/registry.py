"""
工具注册表
"""
from typing import Optional

from app.core.logger import logger
from app.schemas.tool import ToolInfo
from app.tools.base import BaseTool


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._categories: dict[str, list[str]] = {}

    def register(self, tool: BaseTool) -> None:
        """注册工具"""
        self._tools[tool.name] = tool

        if tool.category not in self._categories:
            self._categories[tool.category] = []
        self._categories[tool.category].append(tool.name)

        logger.info(f"Registered tool: {tool.name} in category: {tool.category}")

    def get(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(name)

    def get_all(self) -> list[BaseTool]:
        """获取所有工具"""
        return list(self._tools.values())

    def get_by_category(self, category: str) -> list[BaseTool]:
        """按类别获取工具"""
        tool_names = self._categories.get(category, [])
        return [self._tools[name] for name in tool_names]

    def get_schemas(self, tool_names: Optional[list[str]] = None) -> list[dict]:
        """获取工具 Schema 列表"""
        if tool_names is None:
            return [tool.get_openai_schema() for tool in self._tools.values()]

        schemas = []
        for name in tool_names:
            if name in self._tools:
                schemas.append(self._tools[name].get_openai_schema())
        return schemas

    def get_tool_infos(self) -> list[ToolInfo]:
        """获取工具信息列表"""
        infos = []
        for tool in self._tools.values():
            params_summary = ", ".join(
                f"{p.name}" + ("*" if p.required else "")
                for p in tool.parameters
            )
            infos.append(ToolInfo(
                name=tool.name,
                description=tool.description,
                category=tool.category,
                parameters_summary=params_summary or "无参数",
            ))
        return infos

    def list_tools(self) -> list[str]:
        """列出所有工具名称"""
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        """检查工具是否存在"""
        return name in self._tools


# 全局工具注册表
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """获取工具注册表单例"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
        # 注册默认工具
        _register_default_tools(_tool_registry)
    return _tool_registry


def _register_default_tools(registry: ToolRegistry) -> None:
    """注册默认工具"""
    from app.tools.apple_native import (
        CreateAppleNoteTool,
        CreateAppleReminderTool,
        ListAppleNotesTool,
        ListAppleRemindersTool,
        OpenAppleNoteTool,
        ShowAppleReminderTool,
    )
    from app.tools.browser import (
        ClickTool,
        ScrollTool,
        TakeScreenshotTool,
        TypeTextTool,
    )
    from app.tools.calendar import AddCalendarEventTool
    from app.tools.calculator import CalculatorTool
    from app.tools.files import ReadFileTool
    from app.tools.notes import WriteNoteTool
    from app.tools.todos import AddTodoTool

    # 信息获取类
    registry.register(ReadFileTool())

    # 结构化写入类
    registry.register(WriteNoteTool())
    registry.register(AddTodoTool())
    registry.register(AddCalendarEventTool())
    registry.register(CreateAppleReminderTool())
    registry.register(ListAppleRemindersTool())
    registry.register(CreateAppleNoteTool())
    registry.register(ListAppleNotesTool())
    registry.register(ShowAppleReminderTool())
    registry.register(OpenAppleNoteTool())

    # 网页交互类
    registry.register(ClickTool())
    registry.register(TypeTextTool())
    registry.register(ScrollTool())
    registry.register(TakeScreenshotTool())

    # 辅助类
    registry.register(CalculatorTool())
