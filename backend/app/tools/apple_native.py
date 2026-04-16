"""
Apple 原生应用工具
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Any

from app.core.enums import FailureType
from app.schemas.tool import ToolParameter
from app.tools.base import BaseTool, ToolContext, ToolResult


BACKEND_ROOT = Path(__file__).resolve().parents[2]
NATIVE_DIR = BACKEND_ROOT / "native"
REMINDERS_CLI = NATIVE_DIR / "reminders_cli.swift"
NOTES_CLI = NATIVE_DIR / "notes_cli.py"


async def _run_native_cli(
    command: list[str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )

    stdout_text = stdout.decode("utf-8").strip()
    stderr_text = stderr.decode("utf-8").strip()

    if process.returncode != 0:
        message = stderr_text or stdout_text or f"Native CLI failed with code {process.returncode}"
        try:
            parsed = json.loads(message)
            if isinstance(parsed, dict) and parsed.get("error"):
                message = parsed["error"]
        except json.JSONDecodeError:
            pass
        raise RuntimeError(message)

    if not stdout_text:
        return {}
    return json.loads(stdout_text)


class CreateAppleReminderTool(BaseTool):
    @property
    def name(self) -> str:
        return "create_apple_reminder"

    @property
    def description(self) -> str:
        return "在 macOS 提醒事项中创建一条提醒。"

    @property
    def category(self) -> str:
        return "structured_write"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="title", type="string", description="提醒标题", required=True),
            ToolParameter(name="notes", type="string", description="提醒备注", required=False),
            ToolParameter(name="list_name", type="string", description="提醒事项列表名称", required=False),
            ToolParameter(name="due_date", type="string", description="截止时间，支持 YYYY-MM-DD、YYYY-MM-DD HH:MM 或 ISO8601", required=False),
            ToolParameter(name="priority", type="string", description="优先级：high、medium、low", required=False, enum=["high", "medium", "low"]),
        ]

    async def execute(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        start_time = time.time()
        try:
            result = await _run_native_cli(
                ["swift", str(REMINDERS_CLI), "create"],
                args,
            )
            return self.create_success_result(
                result,
                latency_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            return self.create_error_result(
                str(exc),
                FailureType.TOOL_RUNTIME_ERROR,
                latency_ms=int((time.time() - start_time) * 1000),
            )


class ListAppleRemindersTool(BaseTool):
    @property
    def name(self) -> str:
        return "list_apple_reminders"

    @property
    def description(self) -> str:
        return "读取 macOS 提醒事项中的提醒列表。"

    @property
    def category(self) -> str:
        return "information"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="list_name", type="string", description="可选，指定提醒事项列表", required=False),
            ToolParameter(name="include_completed", type="boolean", description="是否包含已完成提醒", required=False, default=False),
            ToolParameter(name="limit", type="integer", description="最多返回多少条提醒", required=False, default=20),
        ]

    async def execute(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        start_time = time.time()
        payload = {
            "list_name": args.get("list_name"),
            "include_completed": args.get("include_completed", False),
            "limit": args.get("limit", 20),
        }
        try:
            result = await _run_native_cli(
                ["swift", str(REMINDERS_CLI), "list"],
                payload,
            )
            return self.create_success_result(
                result,
                latency_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            return self.create_error_result(
                str(exc),
                FailureType.TOOL_RUNTIME_ERROR,
                latency_ms=int((time.time() - start_time) * 1000),
            )


class CreateAppleNoteTool(BaseTool):
    @property
    def name(self) -> str:
        return "create_apple_note"

    @property
    def description(self) -> str:
        return "在 macOS 备忘录中创建一条笔记。"

    @property
    def category(self) -> str:
        return "structured_write"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="title", type="string", description="笔记标题", required=True),
            ToolParameter(name="content", type="string", description="笔记正文", required=True),
            ToolParameter(name="folder", type="string", description="可选，备忘录文件夹名称", required=False),
        ]

    async def execute(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        start_time = time.time()
        try:
            result = await _run_native_cli(
                ["python3", str(NOTES_CLI), "create"],
                args,
            )
            return self.create_success_result(
                result,
                latency_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            return self.create_error_result(
                str(exc),
                FailureType.TOOL_RUNTIME_ERROR,
                latency_ms=int((time.time() - start_time) * 1000),
            )


class ListAppleNotesTool(BaseTool):
    @property
    def name(self) -> str:
        return "list_apple_notes"

    @property
    def description(self) -> str:
        return "读取 macOS 备忘录中的笔记列表。"

    @property
    def category(self) -> str:
        return "information"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="folder", type="string", description="可选，备忘录文件夹名称", required=False),
            ToolParameter(name="limit", type="integer", description="最多返回多少条笔记", required=False, default=20),
        ]

    async def execute(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        start_time = time.time()
        payload = {
            "folder": args.get("folder"),
            "limit": args.get("limit", 20),
        }
        try:
            result = await _run_native_cli(
                ["python3", str(NOTES_CLI), "list"],
                payload,
            )
            return self.create_success_result(
                result,
                latency_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            return self.create_error_result(
                str(exc),
                FailureType.TOOL_RUNTIME_ERROR,
                latency_ms=int((time.time() - start_time) * 1000),
            )


class ShowAppleReminderTool(BaseTool):
    @property
    def name(self) -> str:
        return "show_apple_reminder"

    @property
    def description(self) -> str:
        return "在 macOS 提醒事项中打开并展示指定提醒。"

    @property
    def category(self) -> str:
        return "information"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="reminder_id",
                type="string",
                description="提醒的标识符，可以是 UUID 或 x-apple-reminder URL",
                required=True,
            ),
        ]

    async def execute(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        start_time = time.time()
        try:
            result = await _run_native_cli(
                ["swift", str(REMINDERS_CLI), "show"],
                args,
            )
            return self.create_success_result(
                result,
                latency_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            return self.create_error_result(
                str(exc),
                FailureType.TOOL_RUNTIME_ERROR,
                latency_ms=int((time.time() - start_time) * 1000),
            )


class OpenAppleNoteTool(BaseTool):
    @property
    def name(self) -> str:
        return "open_apple_note"

    @property
    def description(self) -> str:
        return "在 macOS 备忘录中打开并展示指定笔记。"

    @property
    def category(self) -> str:
        return "information"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="note_id",
                type="string",
                description="备忘录笔记的标识符",
                required=True,
            ),
        ]

    async def execute(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        start_time = time.time()
        try:
            result = await _run_native_cli(
                ["python3", str(NOTES_CLI), "open"],
                args,
            )
            return self.create_success_result(
                result,
                latency_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            return self.create_error_result(
                str(exc),
                FailureType.TOOL_RUNTIME_ERROR,
                latency_ms=int((time.time() - start_time) * 1000),
            )
