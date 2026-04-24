import pytest

from app.core.enums import FailureType
from app.runtime.executor import Executor
from app.runtime.state import AgentState
from app.schemas.action import (
    AgentAction,
    AgentActionType,
    normalize_tool_arguments,
    validate_tool_arguments,
)
from app.tools.registry import get_tool_registry


def test_agent_action_requires_ids() -> None:
    with pytest.raises(ValueError):
        AgentAction(action_type=AgentActionType.TOOL_CALL, step_id="", trace_id="trace")


def test_invalid_json_arguments_are_invalid_format() -> None:
    result = normalize_tool_arguments("{bad json")
    assert result.is_valid is False
    assert result.error_type == FailureType.INVALID_FORMAT.value


def test_missing_tool_argument_is_wrong_args() -> None:
    tool = get_tool_registry().get("write_note")
    assert tool is not None
    result = validate_tool_arguments(tool, {"title": "Only title"})
    assert result.is_valid is False
    assert result.error_type == FailureType.WRONG_ARGS.value


@pytest.mark.asyncio
async def test_failed_tool_call_is_logged_as_action() -> None:
    executor = Executor()
    state = AgentState(task_id="task_schema", instruction="bad args", trajectory_id="trace_schema")

    result = await executor.execute("write_note", {"title": "Missing content"}, state)

    assert result.success is False
    assert result.error_type == FailureType.WRONG_ARGS.value
    assert state.actions
    assert state.actions[-1]["status"] == "failed"
    assert state.actions[-1]["error_type"] == FailureType.WRONG_ARGS.value
