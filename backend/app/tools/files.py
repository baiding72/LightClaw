"""
文件操作工具
"""
import time
from pathlib import Path
from typing import Any

from app.core.enums import FailureType
from app.schemas.tool import ToolParameter
from app.tools.base import BaseTool, ToolContext, ToolResult


class ReadFileTool(BaseTool):
    """读取本地文件工具"""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "读取本地文件的内容。支持文本文件、Markdown 文件等。"

    @property
    def category(self) -> str:
        return "information"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="文件路径（相对于 data 目录或绝对路径）",
                required=True,
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()

        path = args.get("path", "")
        if not path:
            return self.create_error_result(
                "文件路径不能为空",
                FailureType.WRONG_ARGS,
            )

        # 处理相对路径
        file_path = Path(path)
        if not file_path.is_absolute():
            # 尝试在 examples/sample_files 目录下查找
            file_path = Path("examples/sample_files") / path

        if not file_path.exists():
            latency_ms = int((time.time() - start_time) * 1000)
            return self.create_error_result(
                f"文件不存在: {path}",
                FailureType.WRONG_ARGS,
                latency_ms=latency_ms,
            )

        try:
            content = file_path.read_text(encoding="utf-8")
            latency_ms = int((time.time() - start_time) * 1000)

            return self.create_success_result(
                {
                    "path": str(file_path),
                    "content": content[:10000],  # 限制长度
                    "length": len(content),
                    "extension": file_path.suffix,
                },
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return self.create_error_result(
                f"读取文件失败: {str(e)}",
                FailureType.TOOL_RUNTIME_ERROR,
                latency_ms=latency_ms,
            )
