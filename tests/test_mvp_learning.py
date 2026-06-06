"""Learning tests that document the current myClaw Custom ReAct harness behavior.

These tests use a tiny queued chat model to verify agent behavior without external LLM calls.
"""

from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr

from core.agent import create_agent_harness
from core.policy import ToolPolicy
from core.tools.builtins import calculator


class QueueChatModel(BaseChatModel):
    """A deterministic chat model with just enough API for the Custom ReAct harness."""

    _responses: list[AIMessage] = PrivateAttr()
    _seen_messages: list[list[dict]] = PrivateAttr(default_factory=list)
    _bound_tool_names: list[str] = PrivateAttr(default_factory=list)

    def __init__(self, responses: Sequence[AIMessage]):
        super().__init__()
        self._responses = list(responses)

    @property
    def _llm_type(self) -> str:
        return "queue-chat-model"

    @property
    def seen_messages(self) -> list[list[dict]]:
        return self._seen_messages

    @property
    def bound_tool_names(self) -> list[str]:
        return self._bound_tool_names

    def bind_tools(self, tools: Sequence[BaseTool], **kwargs: Any) -> "QueueChatModel":
        # Handle both BaseTool objects and dict schemas
        if tools and hasattr(tools[0], 'name'):
            self._bound_tool_names = [tool.name for tool in tools]
        else:
            # It's a list of dicts (schemas)
            self._bound_tool_names = [t.get("name") for t in tools]
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Convert messages to dict format for Custom harness
        msg_dicts = []
        for msg in messages:
            msg_dict = {"type": type(msg).__name__.lower().replace("message", "")}
            if hasattr(msg, "content"):
                msg_dict["content"] = msg.content
            if hasattr(msg, "name"):
                msg_dict["name"] = msg.name
            msg_dicts.append(msg_dict)
        self._seen_messages.append(msg_dicts)

        if not self._responses:
            raise AssertionError("QueueChatModel has no queued response left")
        return ChatResult(generations=[ChatGeneration(message=self._responses.pop(0))])


def test_direct_answer_injects_system_prompt_and_binds_tools():
    """Test that agent returns direct answer without tools."""
    llm = QueueChatModel([AIMessage(content="MVP can answer without tools.")])
    harness = create_agent_harness(llm, tool_policy=ToolPolicy(mode="off"))

    result = harness.run("hello")

    assert result["answer"] == "MVP can answer without tools."
    # Check system prompt was used - our Custom harness uses 'type' not 'role'
    first_message = llm.seen_messages[0][0]
    assert first_message.get("type") == "system"
    assert "ReAct" in first_message.get("content", "")
    assert {"get_time", "calculator", "echo", "list_office_files", "read_office_file", "write_office_file"}.issubset(
        set(llm.bound_tool_names)
    )


def test_one_tool_call_executes_and_returns_observation():
    """Test that agent can call a tool and get result."""
    llm = QueueChatModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_calculator_1",
                        "name": "calculator",
                        "args": {"expression": "2 + 3 * 4"},
                    }
                ],
            ),
            AIMessage(content="The result is 14."),
        ]
    )
    harness = create_agent_harness(llm, tool_policy=ToolPolicy(mode="off"))

    result = harness.run("calculate 2 + 3 * 4")

    # Check tool was executed
    tool_results = [msg for msg in result["state"].messages if msg.role == "tool"]
    assert len(tool_results) == 1
    assert tool_results[0].name == "calculator"
    assert "14" in tool_results[0].content

    # Check final answer
    assert "14" in result["answer"]
    assert len(llm.seen_messages) == 2


def test_react_loop_with_file_tool():
    """Test that file tools work in the ReAct loop."""
    relative_path = f"test-note-{uuid4().hex[:8]}.txt"
    llm = QueueChatModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_write_file_1",
                        "name": "write_office_file",
                        "args": {
                            "relative_path": relative_path,
                            "content": "hello from ReAct",
                        },
                    }
                ],
            ),
            AIMessage(content="I wrote the note."),
        ]
    )
    harness = create_agent_harness(llm, tool_policy=ToolPolicy(mode="off"))

    result = harness.run("write a note")

    tool_results = [msg for msg in result["state"].messages if msg.role == "tool"]
    assert len(tool_results) == 1
    assert tool_results[0].name == "write_office_file"
    assert "Wrote" in tool_results[0].content
    assert result["answer"] == "I wrote the note."


def test_calculator_is_not_a_strict_arithmetic_parser_badcase():
    """The harness blocks builtins, but still evaluates general Python expressions."""

    assert calculator.invoke({"expression": "'badcase'.upper()"}) == "BADCASE"


def test_multi_turn_conversation_preserves_state():
    """Test that multi-turn conversation works in harness."""
    llm = QueueChatModel(
        [
            AIMessage(content="First answer."),
            AIMessage(content="Second answer."),
        ]
    )
    harness = create_agent_harness(llm, tool_policy=ToolPolicy(mode="off"))

    # First turn
    result1 = harness.run("first question")
    assert result1["answer"] == "First answer."
    assert len(result1["state"].messages) == 2  # user + ai

    # Second turn - harness should continue with same state
    result2 = harness.run("second question")
    assert result2["answer"] == "Second answer."


def test_max_turns_prevents_infinite_loop():
    """Test that max_turns limits the ReAct loop."""
    llm = QueueChatModel(
        [
            AIMessage(
                content="",
                tool_calls=[{"id": "1", "name": "echo", "args": {"message": "loop"}}],
            )
        ]
        * 20  # Too many responses
    )
    harness = create_agent_harness(llm, max_turns=3, tool_policy=ToolPolicy(mode="off"))

    result = harness.run("make me loop")

    assert result["turns"] == 3
    assert "max turns" in result["answer"].lower()
