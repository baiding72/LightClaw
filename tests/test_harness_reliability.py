"""Reliability primitives for context, retry, checkpoints, and tool results."""

from __future__ import annotations

from langchain_core.messages import AIMessage

from core.agent import create_agent_harness
from core.context_guard import compact_tool_result, protect_state
from core.retry import call_with_retry
from core.state import AgentState
from core.tool_result import classify_tool_output
from tests.test_mvp_learning import QueueChatModel


def test_structured_tool_result_classifies_success_and_failure():
    ok = classify_tool_output("save_note", "Note updated: [abc]")
    denied = classify_tool_output("save_note", "Tool execution paused by policy", denied=True)

    assert ok.ok is True
    assert ok.status == "updated"
    assert denied.ok is False
    assert denied.status == "denied"


def test_context_guard_compacts_large_tool_results():
    compacted, changed = compact_tool_result("x" * 10_000, limit=1_000)

    assert changed is True
    assert "omitted" in compacted
    assert len(compacted) < 1_200


def test_context_guard_updates_tool_message_metadata():
    state = AgentState()
    state.add_user_message("read big file")
    state.add_tool_message("read_file", "x" * 10_000)

    report = protect_state(state, tool_result_char_limit=1_000)

    tool_message = [message for message in state.messages if message.role == "tool"][0]
    assert report.compacted_tool_results == 1
    assert tool_message.metadata["context_compacted"] is True
    assert "omitted" in tool_message.content


def test_retry_retries_transient_error_once():
    calls = {"count": 0}

    def flaky() -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("429 rate limit")
        return "ok"

    assert call_with_retry(flaky, attempts=2, base_delay=0) == "ok"
    assert calls["count"] == 2


def test_agent_tool_message_has_structured_metadata():
    llm = QueueChatModel(
        [
            AIMessage(
                content="",
                tool_calls=[{"id": "call_1", "name": "calculator", "args": {"expression": "2+2"}}],
            ),
            AIMessage(content="4"),
        ]
    )
    harness = create_agent_harness(llm)

    result = harness.run("calculate")

    tool_message = [message for message in result["state"].messages if message.role == "tool"][0]
    assert tool_message.metadata["tool_ok"] is True
    assert tool_message.metadata["tool_status"] in {"ok", "updated"}
