"""LLM Provider factory for myClaw."""

import os
from typing import Literal

from langchain_core.language_models import BaseChatModel


def get_provider(
    provider_name: Literal["openai", "anthropic"] = "openai",
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> BaseChatModel:
    """Get a chat model provider instance.

    Args:
        provider_name: The provider to use ("openai" or "anthropic").
        model: Model name. Defaults to provider-specific default.
        api_key: API key. Falls back to environment variable.
        base_url: Base URL for OpenAI-compatible APIs.

    Returns:
        Configured chat model instance.

    Raises:
        ValueError: If required credentials are missing.
    """
    if provider_name == "openai":
        from langchain_openai import ChatOpenAI

        actual_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not actual_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        actual_base_url = base_url or os.environ.get("OPENAI_API_BASE")

        kwargs = {}
        if actual_base_url and "minimax" in actual_base_url.lower():
            # MiniMax's OpenAI-compatible endpoint rejects some OpenAI-only
            # chat settings that langchain-openai may attach around tool calls.
            kwargs["disabled_params"] = {"parallel_tool_calls": None}

        return ChatOpenAI(
            model=model or "gpt-4o",
            api_key=actual_key,
            base_url=actual_base_url,
            **kwargs,
        )

    elif provider_name == "anthropic":
        from langchain_anthropic import ChatAnthropic

        actual_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not actual_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        return ChatAnthropic(
            model=model or "claude-sonnet-4-7-20250514",
            api_key=actual_key,
        )

    else:
        raise ValueError(f"Unsupported provider: {provider_name}")
