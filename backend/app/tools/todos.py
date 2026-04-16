"""
待办事项工具
"""
import time
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select

from app.core.enums import FailureType
from app.db.models import TodoModel
from app.schemas.tool import ToolParameter
from app.tools.base import BaseTool, ToolContext, ToolResult


class AddTodoTool(BaseTool):
    """添加待办事项工具"""

    @property
    def name(self) -> str:
        return "add_todo"

    @property
    def description(self) -> str:
        return "创建一条新的待办事项。"

    @property
    def category(self) -> str:
        return "structured_write"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="title",
                type="string",
                description="待办事项标题",
                required=True,
            ),
            ToolParameter(
                name="description",
                type="string",
                description="待办事项详细描述",
                required=False,
            ),
            ToolParameter(
                name="deadline",
                type="string",
                description="截止日期（格式：YYYY-MM-DD 或 YYYY-MM-DD HH:MM）",
                required=False,
            ),
            ToolParameter(
                name="priority",
                type="string",
                description="优先级：high、medium、low",
                required=False,
                enum=["high", "medium", "low"],
                default="medium",
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()

        title = args.get("title", "")
        description = args.get("description", "")
        deadline = args.get("deadline")
        priority = args.get("priority", "medium")

        if not title:
            return self.create_error_result(
                "待办事项标题不能为空",
                FailureType.WRONG_ARGS,
            )

        if context.db_session is None:
            return self.create_error_result(
                "数据库会话不可用",
                FailureType.TOOL_RUNTIME_ERROR,
            )

        parsed_deadline: Optional[datetime] = None
        if deadline:
            try:
                for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d"]:
                    try:
                        parsed_deadline = datetime.strptime(deadline, fmt)
                        break
                    except ValueError:
                        continue
                if parsed_deadline is None:
                    return self.create_error_result(
                        f"无法解析日期格式: {deadline}，请使用 YYYY-MM-DD 或 YYYY-MM-DD HH:MM 格式",
                        FailureType.WRONG_ARGS,
                    )
            except Exception as e:
                return self.create_error_result(
                    f"日期解析错误: {str(e)}",
                    FailureType.WRONG_ARGS,
                )

        todo = TodoModel(
            title=title,
            description=description or None,
            deadline=parsed_deadline,
            priority=priority,
            status="pending",
        )
        context.db_session.add(todo)
        await context.db_session.commit()
        await context.db_session.refresh(todo)

        latency_ms = int((time.time() - start_time) * 1000)

        return self.create_success_result(
            {
                "todo_id": todo.id,
                "title": todo.title,
                "description": todo.description,
                "deadline": todo.deadline.isoformat() if todo.deadline else None,
                "priority": todo.priority,
                "status": todo.status,
                "created_at": todo.created_at.isoformat(),
                "message": "待办事项创建成功",
            },
            latency_ms=latency_ms,
        )


class ListTodosTool(BaseTool):
    """列出待办事项工具"""

    @property
    def name(self) -> str:
        return "list_todos"

    @property
    def description(self) -> str:
        return "获取待办事项列表。"

    @property
    def category(self) -> str:
        return "information"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="status",
                type="string",
                description="筛选状态：pending、completed、all",
                required=False,
                enum=["pending", "completed", "all"],
                default="all",
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()
        status = args.get("status", "all")

        if context.db_session is None:
            return self.create_error_result(
                "数据库会话不可用",
                FailureType.TOOL_RUNTIME_ERROR,
            )

        query = select(TodoModel).order_by(TodoModel.created_at.desc())
        if status != "all":
            query = query.where(TodoModel.status == status)

        result = await context.db_session.execute(query)
        todos = result.scalars().all()
        latency_ms = int((time.time() - start_time) * 1000)

        return self.create_success_result(
            {
                "todos": [
                    {
                        "id": todo.id,
                        "title": todo.title,
                        "description": todo.description,
                        "deadline": todo.deadline.isoformat() if todo.deadline else None,
                        "priority": todo.priority,
                        "status": todo.status,
                        "created_at": todo.created_at.isoformat(),
                        "updated_at": todo.updated_at.isoformat(),
                    }
                    for todo in todos
                ],
                "total": len(todos),
                "message": "待办列表读取成功",
            },
            latency_ms=latency_ms,
        )
