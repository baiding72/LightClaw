"""
笔记工具
"""
import time
from typing import Any

from sqlalchemy import select

from app.core.enums import FailureType
from app.db.models import NoteModel
from app.schemas.tool import ToolParameter
from app.tools.base import BaseTool, ToolContext, ToolResult


class WriteNoteTool(BaseTool):
    """写入笔记工具"""

    @property
    def name(self) -> str:
        return "write_note"

    @property
    def description(self) -> str:
        return "创建一条新笔记，保存标题和内容。"

    @property
    def category(self) -> str:
        return "structured_write"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="title",
                type="string",
                description="笔记标题",
                required=True,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="笔记内容",
                required=True,
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()

        title = args.get("title", "")
        content = args.get("content", "")

        if not title:
            return self.create_error_result(
                "笔记标题不能为空",
                FailureType.WRONG_ARGS,
            )

        if not content:
            return self.create_error_result(
                "笔记内容不能为空",
                FailureType.WRONG_ARGS,
            )

        if context.db_session is None:
            return self.create_error_result(
                "数据库会话不可用",
                FailureType.TOOL_RUNTIME_ERROR,
            )

        note = NoteModel(title=title, content=content)
        context.db_session.add(note)
        await context.db_session.commit()
        await context.db_session.refresh(note)

        latency_ms = int((time.time() - start_time) * 1000)

        return self.create_success_result(
            {
                "note_id": note.id,
                "title": note.title,
                "content": note.content,
                "created_at": note.created_at.isoformat(),
                "message": "笔记创建成功",
            },
            latency_ms=latency_ms,
        )


class ReadNotesTool(BaseTool):
    """读取笔记列表工具"""

    @property
    def name(self) -> str:
        return "read_notes"

    @property
    def description(self) -> str:
        return "读取已创建的笔记列表。"

    @property
    def category(self) -> str:
        return "information"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="limit",
                type="integer",
                description="返回的最大数量",
                required=False,
                default=10,
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()
        limit = args.get("limit", 10)

        if context.db_session is None:
            return self.create_error_result(
                "数据库会话不可用",
                FailureType.TOOL_RUNTIME_ERROR,
            )

        notes_result = await context.db_session.execute(
            select(NoteModel)
            .order_by(NoteModel.created_at.desc())
            .limit(limit)
        )
        notes = notes_result.scalars().all()
        latency_ms = int((time.time() - start_time) * 1000)

        return self.create_success_result(
            {
                "notes": [
                    {
                        "id": note.id,
                        "title": note.title,
                        "content": note.content,
                        "created_at": note.created_at.isoformat(),
                        "updated_at": note.updated_at.isoformat(),
                    }
                    for note in notes
                ],
                "total": len(notes),
                "message": "笔记列表读取成功",
            },
            latency_ms=latency_ms,
        )
