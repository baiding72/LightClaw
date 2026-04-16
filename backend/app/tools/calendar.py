"""
日历事件工具
"""
import time
from datetime import datetime
from typing import Any, Optional

from app.core.enums import FailureType
from app.schemas.tool import ToolParameter
from app.tools.base import BaseTool, ToolContext, ToolResult


class AddCalendarEventTool(BaseTool):
    """添加日历事件工具"""

    @property
    def name(self) -> str:
        return "add_calendar_event"

    @property
    def description(self) -> str:
        return "创建一个新的日历事件。"

    @property
    def category(self) -> str:
        return "structured_write"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="title",
                type="string",
                description="事件标题",
                required=True,
            ),
            ToolParameter(
                name="start_time",
                type="string",
                description="开始时间（格式：YYYY-MM-DD HH:MM）",
                required=True,
            ),
            ToolParameter(
                name="end_time",
                type="string",
                description="结束时间（格式：YYYY-MM-DD HH:MM）",
                required=True,
            ),
            ToolParameter(
                name="location",
                type="string",
                description="事件地点",
                required=False,
            ),
            ToolParameter(
                name="description",
                type="string",
                description="事件描述",
                required=False,
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()

        title = args.get("title", "")
        start_time_str = args.get("start_time", "")
        end_time_str = args.get("end_time", "")
        location = args.get("location")
        description = args.get("description")

        if not title:
            return self.create_error_result(
                "事件标题不能为空",
                FailureType.WRONG_ARGS,
            )

        if not start_time_str or not end_time_str:
            return self.create_error_result(
                "开始时间和结束时间不能为空",
                FailureType.WRONG_ARGS,
            )

        # 解析时间
        def parse_datetime(dt_str: str) -> Optional[datetime]:
            for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d"]:
                try:
                    return datetime.strptime(dt_str, fmt)
                except ValueError:
                    continue
            return None

        parsed_start = parse_datetime(start_time_str)
        parsed_end = parse_datetime(end_time_str)

        if parsed_start is None:
            return self.create_error_result(
                f"无法解析开始时间: {start_time_str}",
                FailureType.WRONG_ARGS,
            )

        if parsed_end is None:
            return self.create_error_result(
                f"无法解析结束时间: {end_time_str}",
                FailureType.WRONG_ARGS,
            )

        if parsed_end < parsed_start:
            return self.create_error_result(
                "结束时间不能早于开始时间",
                FailureType.WRONG_ARGS,
            )

        latency_ms = int((time.time() - start_time) * 1000)

        return self.create_success_result(
            {
                "event_id": f"event_{context.task_id}_{context.step_index}",
                "title": title,
                "start_time": parsed_start.isoformat(),
                "end_time": parsed_end.isoformat(),
                "location": location,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "message": "日历事件创建成功",
            },
            latency_ms=latency_ms,
        )


class ListCalendarEventsTool(BaseTool):
    """列出日历事件工具"""

    @property
    def name(self) -> str:
        return "list_calendar_events"

    @property
    def description(self) -> str:
        return "获取指定日期范围内的日历事件列表。"

    @property
    def category(self) -> str:
        return "information"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="start_date",
                type="string",
                description="开始日期（格式：YYYY-MM-DD）",
                required=False,
            ),
            ToolParameter(
                name="end_date",
                type="string",
                description="结束日期（格式：YYYY-MM-DD）",
                required=False,
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()
        latency_ms = int((time.time() - start_time) * 1000)

        return self.create_success_result(
            {
                "events": [],
                "total": 0,
                "message": "日历事件列表为空（Mock 实现）",
            },
            latency_ms=latency_ms,
        )
