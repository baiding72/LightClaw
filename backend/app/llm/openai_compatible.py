"""
OpenAI Compatible LLM Adapter

支持 OpenAI API 和兼容的 API（如 GLM、DeepSeek 等）
"""
import asyncio
import time
from typing import Any, Optional

import httpx
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.logger import logger
from app.llm.base import BaseLLMAdapter, ChatMessage, LLMResponse, LLMUsage


class OpenAICompatibleAdapter(BaseLLMAdapter):
    """OpenAI 兼容的 LLM 适配器"""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        settings = get_settings()
        self._model = model or settings.llm_model
        self._api_key = api_key or settings.llm_api_key
        self._base_url = base_url or settings.llm_base_url
        self._max_tokens = settings.llm_max_tokens
        self._temperature = settings.llm_temperature
        self._retry_count = max(1, settings.llm_retry_count)
        self._retry_backoff_ms = max(0, settings.llm_retry_backoff_ms)

        # 初始化客户端
        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            http_client=httpx.AsyncClient(timeout=120.0),
        )

        logger.info(f"Initialized OpenAICompatibleAdapter with model: {self._model}")

    @property
    def model_name(self) -> str:
        return self._model

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """执行聊天请求"""
        start_time = time.time()

        # 转换消息格式
        formatted_messages = []
        for msg in messages:
            msg_dict = {"role": msg.role, "content": msg.content}
            if msg.name:
                msg_dict["name"] = msg.name
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls
            formatted_messages.append(msg_dict)
        has_multimodal_content = any(isinstance(msg.get("content"), list) for msg in formatted_messages)

        # 准备参数
        params: dict[str, Any] = {
            "model": self._model,
            "messages": formatted_messages,
            "temperature": temperature or self._temperature,
            "max_tokens": max_tokens or self._max_tokens,
        }

        # 添加工具
        if tools:
            params["tools"] = self.format_tools_for_llm(tools)
            if tool_choice:
                params["tool_choice"] = tool_choice

        last_error: Optional[Exception] = None
        for attempt in range(1, self._retry_count + 1):
            try:
                response = await self._client.chat.completions.create(**params)

                latency_ms = int((time.time() - start_time) * 1000)

                # 提取使用统计
                usage = LLMUsage(
                    prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                    completion_tokens=response.usage.completion_tokens if response.usage else 0,
                    total_tokens=response.usage.total_tokens if response.usage else 0,
                )

                # 提取内容
                content = response.choices[0].message.content or ""

                # 提取工具调用
                tool_calls = None
                if response.choices[0].message.tool_calls:
                    tool_calls = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in response.choices[0].message.tool_calls
                    ]

                return LLMResponse(
                    content=content,
                    usage=usage,
                    latency_ms=latency_ms,
                    model=response.model,
                    finish_reason=response.choices[0].finish_reason,
                    raw_response={
                        "tool_calls": tool_calls,
                    },
                )
            except Exception as e:
                last_error = e
                if has_multimodal_content:
                    logger.error(
                        "LLM vision payload failed on attempt %s/%s: %s: %s",
                        attempt,
                        self._retry_count,
                        type(e).__name__,
                        e,
                    )
                logger.error(
                    "LLM chat error on attempt %s/%s: %s: %s",
                    attempt,
                    self._retry_count,
                    type(e).__name__,
                    e,
                )
                if attempt >= self._retry_count:
                    break
                await asyncio.sleep((self._retry_backoff_ms / 1000) * attempt)

        raise RuntimeError(
            f"LLM request failed after {self._retry_count} attempts: "
            f"{type(last_error).__name__ if last_error else 'UnknownError'}: {last_error}"
        )

    async def embed(self, text: str) -> list[float]:
        """生成文本嵌入向量"""
        # TODO: 实现真实的 embedding 调用
        # 当前返回一个占位向量
        logger.warning("Embedding not implemented, returning placeholder")
        return [0.0] * 768

    async def close(self) -> None:
        """关闭客户端"""
        await self._client.close()


# 全局适配器实例
_llm_adapter: Optional[OpenAICompatibleAdapter] = None


def get_llm_adapter() -> OpenAICompatibleAdapter:
    """获取 LLM 适配器单例"""
    global _llm_adapter
    if _llm_adapter is None:
        _llm_adapter = OpenAICompatibleAdapter()
    return _llm_adapter


async def reset_llm_adapter() -> None:
    """重置全局 LLM 适配器"""
    global _llm_adapter
    if _llm_adapter is not None:
        await _llm_adapter.close()
    _llm_adapter = None
