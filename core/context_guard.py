"""Context sizing, trimming, and tool-result compaction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEFAULT_MAX_INPUT_TOKENS = 24_000
DEFAULT_TOOL_RESULT_CHAR_LIMIT = 4_000
SUMMARY_CHAR_LIMIT = 2_000


@dataclass(frozen=True)
class ContextGuardReport:
    estimated_tokens_before: int
    estimated_tokens_after: int
    compacted_tool_results: int = 0
    trimmed: bool = False
    summary: str = ""


def estimate_tokens(text: Any) -> int:
    raw = "" if text is None else str(text)
    return max(1, len(raw) // 4)


def estimate_message_tokens(messages: list[dict[str, Any]]) -> int:
    return sum(estimate_tokens(message.get("content", "")) for message in messages)


def compact_tool_result(content: str, limit: int = DEFAULT_TOOL_RESULT_CHAR_LIMIT) -> tuple[str, bool]:
    if len(content) <= limit:
        return content, False
    head = content[: limit // 2]
    tail = content[-limit // 2 :]
    omitted = len(content) - len(head) - len(tail)
    return (
        f"{head}\n\n[myClaw context guard: omitted {omitted} chars from oversized tool result]\n\n{tail}",
        True,
    )


def protect_state(
    state: Any,
    *,
    max_input_tokens: int = DEFAULT_MAX_INPUT_TOKENS,
    tool_result_char_limit: int = DEFAULT_TOOL_RESULT_CHAR_LIMIT,
) -> ContextGuardReport:
    before_messages = [message.to_dict() for message in state.messages]
    before_tokens = estimate_message_tokens(before_messages) + estimate_tokens(state.summary)
    compacted = 0

    for message in state.messages:
        if getattr(message, "role", "") != "tool":
            continue
        next_content, changed = compact_tool_result(message.content, tool_result_char_limit)
        if changed:
            message.metadata["context_compacted"] = True
            message.metadata["original_chars"] = len(message.content)
            message.content = next_content
            compacted += 1

    trimmed = False
    summary = ""
    after_messages = [message.to_dict() for message in state.messages]
    after_tokens = estimate_message_tokens(after_messages) + estimate_tokens(state.summary)
    if after_tokens > max_input_tokens:
        summary = state.trim_context()
        trimmed = bool(summary)
        if summary and len(summary) > SUMMARY_CHAR_LIMIT:
            state.summary = summary[: SUMMARY_CHAR_LIMIT - 3] + "..."
            summary = state.summary

    final_messages = [message.to_dict() for message in state.messages]
    final_tokens = estimate_message_tokens(final_messages) + estimate_tokens(state.summary)
    return ContextGuardReport(
        estimated_tokens_before=before_tokens,
        estimated_tokens_after=final_tokens,
        compacted_tool_results=compacted,
        trimmed=trimmed,
        summary=summary,
    )
