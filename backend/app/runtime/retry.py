"""
Retry / Replan 模块

负责处理失败、重试和重新规划
"""
import json
from typing import Any, Optional

from app.core.enums import FailureType
from app.core.logger import logger
from app.llm import ChatMessage, get_llm_adapter
from app.llm.prompts import REFLECTION_PROMPT
from app.runtime.state import AgentState
from app.schemas.tool import ToolResult


class RecoveryManager:
    """恢复管理器"""

    def __init__(self):
        self.llm = get_llm_adapter()

    async def analyze_failure(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        tool_result: ToolResult,
        state: AgentState,
    ) -> dict[str, Any]:
        """
        分析失败原因

        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            tool_result: 工具结果
            state: 当前状态

        Returns:
            分析结果，包含原因、建议和修复方案
        """
        error_type = FailureType(tool_result.error_type) if tool_result.error_type else FailureType.TOOL_RUNTIME_ERROR

        # 简单分析
        analysis = {
            "error_type": error_type.value,
            "is_recoverable": FailureType.is_recoverable(error_type),
            "suggested_action": self._get_suggested_action(error_type),
            "suggested_fix": None,
        }

        # 如果是参数错误，尝试修复
        if error_type == FailureType.WRONG_ARGS:
            analysis["suggested_fix"] = await self._suggest_args_fix(
                tool_name, tool_args, tool_result.error or "", state
            )

        # 如果是工具选择错误，建议替代工具
        elif error_type == FailureType.WRONG_TOOL:
            analysis["suggested_fix"] = await self._suggest_alternative_tool(
                tool_name, state
            )

        # GUI 相关错误
        elif FailureType.is_gui_failure(error_type):
            analysis["suggested_fix"] = await self._suggest_gui_fix(
                tool_name, tool_args, error_type, state
            )

        logger.info(f"Failure analysis: {analysis}")
        return analysis

    async def reflect(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        tool_result: ToolResult,
        state: AgentState,
    ) -> dict[str, Any]:
        """
        反思失败并生成修复方案

        使用 LLM 进行深度分析

        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            tool_result: 工具结果
            state: 当前状态

        Returns:
            反思结果
        """
        from app.tools import get_tool_registry

        # 获取工具描述
        tool_registry = get_tool_registry()
        tools = tool_registry.get_schemas()
        tools_desc = "\n".join([
            f"- {t['name']}: {t['description']}"
            for t in tools
        ])

        prompt = REFLECTION_PROMPT.format(
            instruction=state.instruction,
            state_summary=state.get_state_summary(),
            tool_name=tool_name,
            tool_args=json.dumps(tool_args, ensure_ascii=False),
            error_type=tool_result.error_type or "unknown",
            error_message=tool_result.error or "Unknown error",
        )

        messages = [
            ChatMessage(role="system", content="你是一个错误分析和修复专家。"),
            ChatMessage(role="user", content=prompt),
        ]

        try:
            response = await self.llm.chat(messages)

            # 记录使用统计
            state.add_token_usage(response.usage.total_tokens)
            state.add_latency(response.latency_ms)

            # 解析反思结果
            reflection = self._parse_reflection(response.content)
            reflection["raw_response"] = response.content

            return reflection

        except Exception as e:
            logger.error(f"Reflection error: {e}")
            return {
                "analysis": "无法分析",
                "suggestion": "重试",
                "next_action": None,
                "error": str(e),
            }

    def _get_suggested_action(self, error_type: FailureType) -> str:
        """获取建议的动作"""
        suggestions = {
            FailureType.WRONG_TOOL: "选择正确的工具",
            FailureType.WRONG_ARGS: "修正参数",
            FailureType.TOOL_RUNTIME_ERROR: "检查环境或重试",
            FailureType.GUI_CLICK_MISS: "检查元素是否存在",
            FailureType.GUI_WRONG_ELEMENT: "确认正确的目标元素",
            FailureType.GUI_STATE_STALE: "刷新页面或重新导航",
            FailureType.STATE_LOSS_AFTER_NAVIGATION: "重新获取页面状态",
            FailureType.PLANNING_ERROR: "重新规划任务",
        }
        return suggestions.get(error_type, "分析错误并尝试修复")

    async def _suggest_args_fix(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        error_msg: str,
        state: AgentState,
    ) -> Optional[dict[str, Any]]:
        """建议参数修复"""
        # 简单实现：返回空
        # TODO: 使用 LLM 分析参数错误并建议修复
        return None

    async def _suggest_alternative_tool(
        self,
        tool_name: str,
        state: AgentState,
    ) -> Optional[str]:
        """建议替代工具"""
        # 简单实现：返回空
        # TODO: 根据任务上下文建议替代工具
        return None

    async def _suggest_gui_fix(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        error_type: FailureType,
        state: AgentState,
    ) -> Optional[dict[str, Any]]:
        """建议 GUI 修复"""
        # 简单实现
        if error_type == FailureType.GUI_CLICK_MISS:
            return {"suggestion": "尝试使用更精确的选择器或先截图查看页面"}
        elif error_type == FailureType.GUI_STATE_STALE:
            return {"suggestion": "等待页面加载完成后再操作"}
        return None

    def _parse_reflection(self, response: str) -> dict[str, Any]:
        """解析反思响应"""
        result = {
            "analysis": "",
            "suggestion": "",
            "next_action": None,
        }

        try:
            lines = response.strip().split("\n")
            current_section = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if "原因" in line:
                    current_section = "analysis"
                    continue
                elif "修复方案" in line or "建议" in line:
                    current_section = "suggestion"
                    continue
                elif "下一步" in line:
                    current_section = "next_action"
                    continue

                if current_section == "analysis":
                    result["analysis"] += line + " "
                elif current_section == "suggestion":
                    result["suggestion"] += line + " "
                elif current_section == "next_action":
                    if line.startswith("-") or line.startswith("*"):
                        result["next_action"] = line.lstrip("-* ").strip()

            result["analysis"] = result["analysis"].strip()
            result["suggestion"] = result["suggestion"].strip()

        except Exception as e:
            logger.warning(f"Failed to parse reflection: {e}")
            result["analysis"] = response

        return result

    async def generate_recovery_plan(
        self,
        state: AgentState,
        analysis: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """
        生成恢复计划

        Args:
            state: 当前状态
            analysis: 失败分析

        Returns:
            恢复计划
        """
        if not analysis.get("is_recoverable"):
            return None

        return {
            "action": "retry_with_fix",
            "tool_name": None,  # 稍后由 planner 决定
            "tool_args": None,
            "reason": analysis.get("suggested_action"),
        }
