"""
Planner 模块

负责分析任务、制定计划
"""
import json
from typing import Any, Optional

from app.core.logger import logger
from app.llm import ChatMessage, get_llm_adapter
from app.llm.prompts import PLANNING_PROMPT, format_tools_description
from app.runtime.state import AgentState
from app.tools import get_tool_registry


class Planner:
    """任务规划器"""

    def __init__(self):
        self.llm = get_llm_adapter()
        self.tool_registry = get_tool_registry()

    async def plan(
        self,
        instruction: str,
        state: AgentState,
        available_tools: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        分析任务并制定计划

        Args:
            instruction: 用户指令
            state: 当前状态
            available_tools: 可用工具列表

        Returns:
            计划结果，包含理解、步骤和预期结果
        """
        # 获取工具描述
        tools = self.tool_registry.get_schemas(available_tools)
        tools_description = format_tools_description(tools)

        # 构建提示
        prompt = PLANNING_PROMPT.format(
            instruction=instruction,
            state_summary=state.get_state_summary(),
            tools_description=tools_description,
        )

        messages = [
            ChatMessage(role="system", content="你是一个任务规划专家。"),
            ChatMessage(role="user", content=prompt),
        ]

        try:
            response = await self.llm.chat(messages)

            # 记录 token 使用
            state.add_token_usage(response.usage.total_tokens)
            state.add_latency(response.latency_ms)

            # 解析响应
            plan_result = self._parse_plan_response(response.content)

            logger.info(f"Planning completed for task: {state.task_id}")
            return plan_result

        except Exception as e:
            logger.error(f"Planning error: {e}")
            return {
                "understanding": instruction,
                "steps": ["执行任务"],
                "expected_result": "完成任务",
                "error": str(e),
            }

    def _parse_plan_response(self, response: str) -> dict[str, Any]:
        """解析计划响应"""
        result = {
            "understanding": "",
            "steps": [],
            "expected_result": "",
        }

        try:
            # 简单解析
            lines = response.strip().split("\n")
            current_section = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if "任务理解" in line or "1." in line:
                    current_section = "understanding"
                    continue
                elif "执行计划" in line or "2." in line:
                    current_section = "steps"
                    continue
                elif "预期结果" in line or "3." in line:
                    current_section = "expected_result"
                    continue

                if current_section == "understanding":
                    result["understanding"] += line + " "
                elif current_section == "steps":
                    if line.startswith("-") or line.startswith("*"):
                        result["steps"].append(line.lstrip("-* ").strip())
                elif current_section == "expected_result":
                    result["expected_result"] += line + " "

            # 清理
            result["understanding"] = result["understanding"].strip()
            result["expected_result"] = result["expected_result"].strip()

            if not result["steps"]:
                result["steps"] = ["直接执行任务"]

        except Exception as e:
            logger.warning(f"Failed to parse plan response: {e}")
            result["understanding"] = response

        return result

    async def decide_next_action(
        self,
        state: AgentState,
        available_tools: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        决定下一步动作

        这是 Planner 的核心方法，决定下一步应该调用什么工具

        Args:
            state: 当前状态
            available_tools: 可用工具列表

        Returns:
            动作决策，包含工具名和参数
        """
        # 获取工具 schema
        tools = self.tool_registry.get_schemas(available_tools)

        # 构建系统提示
        from app.llm.prompts import SYSTEM_PROMPT

        system_prompt = SYSTEM_PROMPT.format(
            tools_description=format_tools_description(tools),
            state_summary=state.get_state_summary(),
        )

        # 构建消息
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=f"用户指令：{state.instruction}\n\n请选择合适的工具执行下一步操作。"),
        ]

        # 添加历史上下文
        if state.observations:
            recent_obs = state.observations[-3:]
            for obs in recent_obs:
                messages.append(ChatMessage(role="assistant", content=f"观察：{obs}"))

        try:
            response = await self.llm.chat(
                messages,
                tools=tools,
                tool_choice="auto",
            )

            # 记录使用统计
            state.add_token_usage(response.usage.total_tokens)
            state.add_latency(response.latency_ms)

            # 提取思考内容
            thought = response.content

            # 检查是否有工具调用
            tool_calls = response.raw_response.get("tool_calls") if response.raw_response else None

            if tool_calls:
                # 解析工具调用
                tool_call = tool_calls[0]
                tool_name = tool_call["function"]["name"]
                tool_args = json.loads(tool_call["function"]["arguments"])

                return {
                    "thought": thought,
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                }
            else:
                # 没有工具调用，可能是总结或询问
                return {
                    "thought": thought,
                    "tool_name": None,
                    "tool_args": None,
                    "response": thought,
                }

        except Exception as e:
            logger.error(f"Error deciding next action: {e}")
            return {
                "thought": f"决策出错: {str(e)}",
                "tool_name": None,
                "tool_args": None,
                "error": str(e),
            }
