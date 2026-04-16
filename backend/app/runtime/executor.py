"""
Executor 模块

负责执行工具调用
"""
import time
from typing import Any, Optional

from app.core.enums import FailureType
from app.core.logger import logger
from app.db.session import async_session_maker
from app.runtime.state import AgentState
from app.schemas.tool import ToolResult
from app.tools import ToolContext, get_tool_registry


class Executor:
    """工具执行器"""

    def __init__(self):
        self.tool_registry = get_tool_registry()

    async def execute(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        state: AgentState,
        browser_page: Optional[Any] = None,
        screenshot_dir: Optional[str] = None,
    ) -> ToolResult:
        """
        执行工具调用

        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            state: 当前状态
            browser_page: Playwright 页面对象（可选）
            screenshot_dir: 截图目录（可选）

        Returns:
            工具执行结果
        """
        start_time = time.time()

        # 获取工具
        tool = self.tool_registry.get(tool_name)
        if not tool:
            latency_ms = int((time.time() - start_time) * 1000)
            result = ToolResult(
                success=False,
                error=f"未找到工具: {tool_name}",
                error_type=FailureType.WRONG_TOOL.value,
                latency_ms=latency_ms,
            )
            state.add_tool_call(tool_name, tool_args, error=result.error)
            state.add_error(FailureType.WRONG_TOOL.value, result.error)
            return result

        # 验证参数
        is_valid, error_msg = tool.validate_args(tool_args)
        if not is_valid:
            latency_ms = int((time.time() - start_time) * 1000)
            result = ToolResult(
                success=False,
                error=error_msg,
                error_type=FailureType.WRONG_ARGS.value,
                latency_ms=latency_ms,
            )
            state.add_tool_call(tool_name, tool_args, error=result.error)
            state.add_error(FailureType.WRONG_ARGS.value, result.error)
            return result

        try:
            async with async_session_maker() as session:
                context = ToolContext(
                    task_id=state.task_id,
                    step_index=state.current_step,
                    trajectory_id=state.trajectory_id,
                    screenshot_dir=screenshot_dir,
                    browser_page=browser_page,
                    db_session=session,
                )

                # 执行工具
                result = await tool.execute(tool_args, context)

            # 记录工具调用
            state.add_tool_call(
                tool_name,
                tool_args,
                result=result.result if result.success else None,
                error=result.error if not result.success else None,
            )

            # 记录 GUI 动作
            if tool.category == "browser" and result.success:
                state.add_gui_action(
                    action_type=tool_name,
                    target=tool_args.get("selector", ""),
                    success=True,
                    details=tool_args,
                )

            # 记录错误
            if not result.success and result.error_type:
                state.add_error(result.error_type, result.error or "Unknown error")

            # 更新延迟统计
            state.add_latency(result.latency_ms or 0)

            logger.info(
                f"Tool execution: {tool_name}, success: {result.success}, "
                f"latency: {result.latency_ms}ms"
            )

            return result

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_msg = f"工具执行异常: {str(e)}"
            logger.error(error_msg)

            result = ToolResult(
                success=False,
                error=error_msg,
                error_type=FailureType.TOOL_RUNTIME_ERROR.value,
                latency_ms=latency_ms,
            )

            state.add_tool_call(tool_name, tool_args, error=error_msg)
            state.add_error(FailureType.TOOL_RUNTIME_ERROR.value, error_msg)

            return result

    async def execute_with_retry(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        state: AgentState,
        max_retries: int = 3,
        browser_page: Optional[Any] = None,
        screenshot_dir: Optional[str] = None,
    ) -> ToolResult:
        """
        带重试的工具执行

        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            state: 当前状态
            max_retries: 最大重试次数
            browser_page: Playwright 页面对象
            screenshot_dir: 截图目录

        Returns:
            工具执行结果
        """
        result = await self.execute(
            tool_name, tool_args, state, browser_page, screenshot_dir
        )

        if result.success:
            return result

        # 检查是否可恢复
        if result.error_type:
            try:
                failure_type = FailureType(result.error_type)
                if not FailureType.is_recoverable(failure_type):
                    return result
            except ValueError:
                pass

        # 重试逻辑
        for attempt in range(max_retries):
            state.retry_count += 1
            logger.info(f"Retrying tool {tool_name}, attempt {attempt + 1}/{max_retries}")

            # 等待一段时间
            await self._wait(1000 * (attempt + 1))

            # 重试执行
            result = await self.execute(
                tool_name, tool_args, state, browser_page, screenshot_dir
            )

            if result.success:
                state.successful_recoveries += 1
                return result

        return result

    async def _wait(self, ms: int) -> None:
        """等待指定毫秒数"""
        import asyncio
        await asyncio.sleep(ms / 1000)
