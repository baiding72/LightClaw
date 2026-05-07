"""Tool skill registry with progressive loading.

A skill groups related tools and exposes lightweight metadata before importing
or instantiating the actual tool classes. This keeps planner/runtime code
compatible with the old tool registry while allowing category-level loading.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.tools.base import BaseTool

ToolFactory = Callable[[], BaseTool]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    factory: ToolFactory


@dataclass
class ToolSkill:
    skill_id: str
    name: str
    description: str
    category: str
    trigger_hints: list[str]
    tool_specs: list[ToolSpec]
    loaded: bool = False
    tool_names: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.tool_names = [spec.name for spec in self.tool_specs]

    def load_tools(self) -> list[BaseTool]:
        self.loaded = True
        return [spec.factory() for spec in self.tool_specs]


def build_default_tool_skills() -> list[ToolSkill]:
    """Declare built-in LightClaw tool skills without instantiating tools."""
    return [
        ToolSkill(
            skill_id="information_retrieval",
            name="Information Retrieval",
            description="Read local files and existing internal artifacts.",
            category="information",
            trigger_hints=["read", "inspect", "load file", "list notes", "list todos"],
            tool_specs=[
                ToolSpec("read_file", _read_file_tool),
                ToolSpec("read_notes", _read_notes_tool),
                ToolSpec("list_todos", _list_todos_tool),
                ToolSpec("list_calendar_events", _list_calendar_events_tool),
            ],
        ),
        ToolSkill(
            skill_id="structured_memory_write",
            name="Structured Memory Write",
            description="Write notes, todos, and calendar-like structured artifacts.",
            category="structured_write",
            trigger_hints=["create todo", "write note", "calendar", "reminder"],
            tool_specs=[
                ToolSpec("write_note", _write_note_tool),
                ToolSpec("add_todo", _add_todo_tool),
                ToolSpec("add_calendar_event", _add_calendar_event_tool),
            ],
        ),
        ToolSkill(
            skill_id="apple_native_apps",
            name="Apple Native Apps",
            description="Create, list, and show macOS Reminders and Notes artifacts.",
            category="native_app",
            trigger_hints=["apple reminder", "apple note", "mac reminders", "mac notes"],
            tool_specs=[
                ToolSpec("create_apple_reminder", _create_apple_reminder_tool),
                ToolSpec("list_apple_reminders", _list_apple_reminders_tool),
                ToolSpec("create_apple_note", _create_apple_note_tool),
                ToolSpec("list_apple_notes", _list_apple_notes_tool),
                ToolSpec("show_apple_reminder", _show_apple_reminder_tool),
                ToolSpec("open_apple_note", _open_apple_note_tool),
            ],
        ),
        ToolSkill(
            skill_id="browser_gui_control",
            name="Browser GUI Control",
            description="Click, type, select, scroll, and screenshot browser pages.",
            category="browser",
            trigger_hints=["click", "type", "scroll", "select", "screenshot", "form"],
            tool_specs=[
                ToolSpec("click", _click_tool),
                ToolSpec("type_text", _type_text_tool),
                ToolSpec("scroll", _scroll_tool),
                ToolSpec("select_option", _select_option_tool),
                ToolSpec("take_screenshot", _take_screenshot_tool),
            ],
        ),
        ToolSkill(
            skill_id="utility_reasoning",
            name="Utility Reasoning",
            description="Deterministic helper tools such as calculator.",
            category="utility",
            trigger_hints=["calculate", "compute", "math"],
            tool_specs=[
                ToolSpec("calculator", _calculator_tool),
            ],
        ),
    ]


def _read_file_tool() -> BaseTool:
    from app.tools.files import ReadFileTool

    return ReadFileTool()


def _read_notes_tool() -> BaseTool:
    from app.tools.notes import ReadNotesTool

    return ReadNotesTool()


def _list_todos_tool() -> BaseTool:
    from app.tools.todos import ListTodosTool

    return ListTodosTool()


def _list_calendar_events_tool() -> BaseTool:
    from app.tools.calendar import ListCalendarEventsTool

    return ListCalendarEventsTool()


def _write_note_tool() -> BaseTool:
    from app.tools.notes import WriteNoteTool

    return WriteNoteTool()


def _add_todo_tool() -> BaseTool:
    from app.tools.todos import AddTodoTool

    return AddTodoTool()


def _add_calendar_event_tool() -> BaseTool:
    from app.tools.calendar import AddCalendarEventTool

    return AddCalendarEventTool()


def _create_apple_reminder_tool() -> BaseTool:
    from app.tools.apple_native import CreateAppleReminderTool

    return CreateAppleReminderTool()


def _list_apple_reminders_tool() -> BaseTool:
    from app.tools.apple_native import ListAppleRemindersTool

    return ListAppleRemindersTool()


def _create_apple_note_tool() -> BaseTool:
    from app.tools.apple_native import CreateAppleNoteTool

    return CreateAppleNoteTool()


def _list_apple_notes_tool() -> BaseTool:
    from app.tools.apple_native import ListAppleNotesTool

    return ListAppleNotesTool()


def _show_apple_reminder_tool() -> BaseTool:
    from app.tools.apple_native import ShowAppleReminderTool

    return ShowAppleReminderTool()


def _open_apple_note_tool() -> BaseTool:
    from app.tools.apple_native import OpenAppleNoteTool

    return OpenAppleNoteTool()


def _click_tool() -> BaseTool:
    from app.tools.browser import ClickTool

    return ClickTool()


def _type_text_tool() -> BaseTool:
    from app.tools.browser import TypeTextTool

    return TypeTextTool()


def _scroll_tool() -> BaseTool:
    from app.tools.browser import ScrollTool

    return ScrollTool()


def _select_option_tool() -> BaseTool:
    from app.tools.browser import SelectOptionTool

    return SelectOptionTool()


def _take_screenshot_tool() -> BaseTool:
    from app.tools.browser import TakeScreenshotTool

    return TakeScreenshotTool()


def _calculator_tool() -> BaseTool:
    from app.tools.calculator import CalculatorTool

    return CalculatorTool()
