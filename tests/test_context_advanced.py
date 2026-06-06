"""CyberClaw context trimming tests migrated to myClaw AgentState."""

from __future__ import annotations

from core.state import AgentState


def test_trim_noop_when_under_threshold():
    state = AgentState()
    state.add_system_message("system")
    state.add_user_message("user 1")
    state.add_ai_message("ai 1")

    assert state.trim_context() == ""
    assert len(state.messages) == 3


def test_trim_discards_old_turns_and_keeps_recent_user_turns():
    state = AgentState()
    state.add_system_message("system")
    for index in range(25):
        state.add_user_message(f"user {index}")
        state.add_ai_message(f"ai {index}")

    summary = state.trim_context()

    assert summary
    assert state.summary == summary
    assert len([message for message in state.messages if message.role == "user"]) == 10
    assert state.messages[0].content == "user 15"
    assert state.messages[-1].content == "ai 24"


def test_trim_empty_messages_is_noop():
    state = AgentState()

    assert state.trim_context() == ""
    assert state.messages == []


def test_trim_keeps_tool_messages_inside_recent_turns():
    state = AgentState()
    for index in range(15):
        state.add_user_message(f"user {index}")
        state.add_ai_message(f"ai {index}", tool_calls=[{"id": f"call_{index}", "name": "echo", "args": {"message": str(index)}}])
        state.add_tool_message("echo", f"tool {index}", tool_call_id=f"call_{index}")

    summary = state.trim_context()

    assert summary
    assert any(message.role == "tool" and message.content == "tool 14" for message in state.messages)
    assert not any(message.content == "tool 0" for message in state.messages)


def test_count_turns_counts_user_messages():
    state = AgentState()
    state.add_system_message("system")
    state.add_user_message("u1")
    state.add_ai_message("a1")
    state.add_tool_message("echo", "tool", tool_call_id="1")
    state.add_user_message("u2")

    assert state.count_turns() == 2

