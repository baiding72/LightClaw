"""
LLM 基础接口
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class LLMUsage:
    """LLM 使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: "LLMUsage") -> "LLMUsage":
        return LLMUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    usage: LLMUsage
    latency_ms: int
    model: str
    finish_reason: Optional[str] = None
    raw_response: Optional[dict[str, Any]] = None


@dataclass
class ChatMessage:
    """聊天消息"""
    role: str  # system, user, assistant, tool
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None


class BaseLLMAdapter(ABC):
    """LLM 适配器基类"""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        执行聊天请求

        Args:
            messages: 消息列表
            tools: 可用工具列表（OpenAI 格式）
            tool_choice: 工具选择策略
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            LLM 响应
        """
        pass

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """
        生成文本嵌入向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """获取模型名称"""
        pass

    def format_tools_for_llm(
        self,
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        格式化工具定义供 LLM 使用

        Args:
            tools: 工具定义列表

        Returns:
            OpenAI 格式的工具定义
        """
        formatted_tools = []
        for tool in tools:
            formatted_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters", {}),
                },
            })
        return formatted_tools
