"""
Observer 模块

负责观察执行结果、总结状态变化
"""
from typing import Any, Optional

from app.core.logger import logger
from app.llm import ChatMessage, get_llm_adapter
from app.llm.prompts import OBSERVATION_PROMPT
from app.runtime.state import AgentState
from app.schemas.tool import ToolResult


class Observer:
    """执行观察器"""

    def __init__(self):
        self.llm = get_llm_adapter()

    async def observe(
        self,
        tool_name: str,
        tool_result: ToolResult,
        state: AgentState,
    ) -> str:
        """
        观察执行结果

        Args:
            tool_name: 执行的工具名称
            tool_result: 工具执行结果
            state: 当前状态

        Returns:
            观察总结
        """
        # 构建结果描述
        result_desc = self._format_result(tool_result)

        # 使用 LLM 总结（可选）
        if tool_result.success:
            # 简单总结
            observation = f"成功执行 {tool_name}。{result_desc}"
        else:
            observation = f"执行 {tool_name} 失败。错误: {tool_result.error}"

        # 添加到状态
        state.add_observation(observation)

        # 更新页面状态
        if tool_result.success and tool_result.result:
            self._update_page_state(tool_name, tool_result.result, state)

        logger.info(f"Observation: {observation[:200]}")
        return observation

    async def observe_with_llm(
        self,
        tool_name: str,
        tool_result: ToolResult,
        state: AgentState,
    ) -> str:
        """
        使用 LLM 进行深度观察

        Args:
            tool_name: 执行的工具名称
            tool_result: 工具执行结果
            state: 当前状态

        Returns:
            观察总结
        """
        prompt = OBSERVATION_PROMPT.format(
            step_index=state.current_step,
            tool_name=tool_name,
            tool_result=self._format_result(tool_result),
        )

        messages = [
            ChatMessage(role="system", content="你是一个执行结果分析专家。"),
            ChatMessage(role="user", content=prompt),
        ]

        try:
            response = await self.llm.chat(messages)
            observation = response.content

            # 记录使用统计
            state.add_token_usage(response.usage.total_tokens)
            state.add_latency(response.latency_ms)

        except Exception as e:
            logger.warning(f"LLM observation failed: {e}")
            observation = f"执行 {tool_name}。{self._format_result(tool_result)}"

        state.add_observation(observation)
        return observation

    def _format_result(self, result: ToolResult) -> str:
        """格式化工具结果"""
        if result.success:
            if result.result:
                if isinstance(result.result, dict):
                    # 提取关键信息
                    keys = list(result.result.keys())[:5]
                    return f"结果包含: {', '.join(keys)}"
                else:
                    return str(result.result)[:200]
            return "操作成功"
        else:
            return f"错误: {result.error}"

    def _update_page_state(
        self,
        tool_name: str,
        result: dict[str, Any],
        state: AgentState,
    ) -> None:
        """更新页面状态"""
        # 根据 URL 更新
        if "url" in result:
            state.current_url = result["url"]
        if "title" in result:
            state.current_page_title = result["title"]

        # 记录最后结果
        state.last_tool_result = result

    def should_continue(self, state: AgentState) -> tuple[bool, Optional[str]]:
        """
        判断是否应该继续执行

        Args:
            state: 当前状态

        Returns:
            (是否继续, 原因)
        """
        # 检查步骤限制
        if state.current_step >= state.max_steps:
            return False, "达到最大步骤限制"

        # 检查是否已完成
        if state.is_completed or state.is_failed:
            return False, state.final_outcome or "任务已结束"

        # 检查错误次数
        if len(state.errors) > 5:
            return False, "错误次数过多"

        return True, None

    def check_task_completion(
        self,
        state: AgentState,
        tool_result: ToolResult,
    ) -> Optional[str]:
        """
        检查任务是否完成

        Args:
            state: 当前状态
            tool_result: 最后的工具结果

        Returns:
            如果完成，返回完成原因；否则返回 None
        """
        # 检查特定工具的完成标志
        if tool_result.success:
            # 写入类工具通常意味着任务进展
            if tool_result.result and isinstance(tool_result.result, dict):
                message = tool_result.result.get("message", "")
                if "成功" in message or "完成" in message:
                    # 可能是任务完成的标志
                    # 但需要更多信息判断
                    pass

        return None
