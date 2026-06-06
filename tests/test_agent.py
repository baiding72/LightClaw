"""Basic tests for myClaw agent - Custom ReAct harness."""

import pytest

from core.agent import create_agent_harness, AgentHarness
from core.state import AgentState
from core.tools.builtins import ALL_TOOLS, get_time, calculator, echo


class TestBuiltinTools:
    """Test the built-in tools."""

    def test_get_time(self):
        """Test the get_time tool returns a string."""
        result = get_time.invoke({})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_calculator(self):
        """Test the calculator tool."""
        assert calculator.invoke({"expression": "1+1"}) == "2"
        assert calculator.invoke({"expression": "2*3"}) == "6"
        assert calculator.invoke({"expression": "10-4"}) == "6"

    def test_echo(self):
        """Test the echo tool."""
        result = echo.invoke({"message": "hello"})
        assert result == "Echo: hello"


class TestAgentState:
    """Test agent state structure."""

    def test_state_has_messages(self):
        """State should have messages field."""
        state = AgentState()
        assert hasattr(state, "messages")
        assert hasattr(state, "summary")

    def test_add_user_message(self):
        """Test adding user messages."""
        state = AgentState()
        state.add_user_message("Hello")
        assert len(state.messages) == 1
        assert state.messages[0].role == "user"
        assert state.messages[0].content == "Hello"

    def test_add_ai_message(self):
        """Test adding AI messages."""
        state = AgentState()
        state.add_ai_message("Hello", tool_calls=[{"name": "test", "args": {}}])
        assert len(state.messages) == 1
        assert state.messages[0].role == "assistant"
        assert state.messages[0].content == "Hello"
        assert state.messages[0].tool_calls == [{"name": "test", "args": {}}]

    def test_add_tool_message(self):
        """Test adding tool messages."""
        state = AgentState()
        state.add_tool_message(name="calculator", content="2", tool_call_id="call_1")
        assert len(state.messages) == 1
        assert state.messages[0].role == "tool"
        assert state.messages[0].name == "calculator"
        assert state.messages[0].content == "2"
        assert state.messages[0].tool_call_id == "call_1"


class TestAgentHarness:
    """Test the custom agent harness."""

    def test_harness_creation(self):
        """Test that create_agent_harness returns a harness instance."""
        from core.provider import get_provider
        import os

        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            pytest.skip("No API key available")

        provider = "openai" if os.environ.get("OPENAI_API_KEY") else "anthropic"
        llm = get_provider(provider)
        harness = create_agent_harness(llm)
        assert harness is not None
        assert isinstance(harness, AgentHarness)

    def test_tools_are_registered(self):
        """Test that tools are properly registered."""
        tool_names = [t.name for t in ALL_TOOLS]
        assert "get_time" in tool_names
        assert "calculator" in tool_names
        assert "echo" in tool_names
        assert "search_local_sources" not in tool_names
