from app.tools.base import BaseTool, ToolContext
from app.tools.apple_native import (
    CreateAppleNoteTool,
    CreateAppleReminderTool,
    ListAppleNotesTool,
    ListAppleRemindersTool,
    OpenAppleNoteTool,
    ShowAppleReminderTool,
)
from app.tools.registry import ToolRegistry, get_tool_registry
from app.tools.browser import (
    ClickTool,
    ScrollTool,
    SelectOptionTool,
    TakeScreenshotTool,
    TypeTextTool,
)
from app.tools.calendar import AddCalendarEventTool, ListCalendarEventsTool
from app.tools.calculator import CalculatorTool
from app.tools.files import ReadFileTool
from app.tools.notes import ReadNotesTool, WriteNoteTool
from app.tools.search_web import OpenUrlTool, ReadPageTool, SearchWebTool
from app.tools.todos import AddTodoTool, ListTodosTool

__all__ = [
    "BaseTool",
    "ToolContext",
    "ToolRegistry",
    "get_tool_registry",
    "CreateAppleReminderTool",
    "ListAppleRemindersTool",
    "CreateAppleNoteTool",
    "ListAppleNotesTool",
    "ShowAppleReminderTool",
    "OpenAppleNoteTool",
    # Browser tools
    "ClickTool",
    "TypeTextTool",
    "ScrollTool",
    "TakeScreenshotTool",
    "SelectOptionTool",
    # Calendar tools
    "AddCalendarEventTool",
    "ListCalendarEventsTool",
    # Calculator
    "CalculatorTool",
    # File tools
    "ReadFileTool",
    # Note tools
    "WriteNoteTool",
    "ReadNotesTool",
    # Search tools
    "SearchWebTool",
    "OpenUrlTool",
    "ReadPageTool",
    # Todo tools
    "AddTodoTool",
    "ListTodosTool",
]
