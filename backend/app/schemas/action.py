"""
Unified agent action schema.

This module is intentionally additive: existing ToolCall, ToolResult and
trajectory schemas remain valid, while runtime/eval/export code can use this
single envelope for tool-use, self-correction and GUI grounding events.
"""
from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import FailureType


class AgentActionType(str, Enum):
    TOOL_CALL = "tool_call"
    ASK_USER = "ask_user"
    FINAL_ANSWER = "final_answer"
    REVISE = "revise"
    SELF_CORRECTION = "self_correction"
    GUI_CLICK = "gui_click"
    GUI_GROUNDING = "gui_grounding"


class AgentActionStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class ToolArgumentValidation(BaseModel):
    """Normalized tool argument validation result."""

    is_valid: bool
    arguments: dict[str, Any] = Field(default_factory=dict)
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class AgentAction(BaseModel):
    """A single normalized action emitted by the planner/runtime."""

    model_config = ConfigDict(use_enum_values=True)

    action_type: AgentActionType
    step_id: str
    trace_id: str
    action_name: Optional[str] = None
    tool_name: Optional[str] = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    observation: Optional[Any] = None
    status: AgentActionStatus = AgentActionStatus.PLANNED
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    latency_ms: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("step_id", "trace_id")
    @classmethod
    def _non_empty_id(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("step_id and trace_id must be non-empty")
        return value

    def mark_running(self) -> "AgentAction":
        self.status = AgentActionStatus.RUNNING
        return self

    def mark_success(
        self,
        *,
        observation: Optional[Any] = None,
        latency_ms: Optional[int] = None,
    ) -> "AgentAction":
        self.status = AgentActionStatus.SUCCESS
        if observation is not None:
            self.observation = observation
        self.latency_ms = latency_ms
        self.error_type = None
        self.error_message = None
        return self

    def mark_failed(
        self,
        *,
        error_type: str,
        error_message: str,
        observation: Optional[Any] = None,
        latency_ms: Optional[int] = None,
    ) -> "AgentAction":
        self.status = AgentActionStatus.FAILED
        self.error_type = error_type
        self.error_message = error_message
        if observation is not None:
            self.observation = observation
        self.latency_ms = latency_ms
        return self


def normalize_tool_arguments(raw_arguments: Any) -> ToolArgumentValidation:
    """
    Normalize planner-provided tool arguments.

    The runtime may receive a dict from structured output or a raw JSON string
    from an LLM/tool-call adapter. Invalid format is separated from wrong_args
    so later reward/export can distinguish parser failures from schema failures.
    """
    if raw_arguments is None:
        return ToolArgumentValidation(
            is_valid=False,
            error_type=FailureType.INVALID_FORMAT.value,
            error_message="Tool arguments are missing; expected a JSON object.",
        )

    if isinstance(raw_arguments, str):
        try:
            raw_arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            return ToolArgumentValidation(
                is_valid=False,
                error_type=FailureType.INVALID_FORMAT.value,
                error_message=f"Invalid JSON tool arguments: {exc.msg}",
            )

    if not isinstance(raw_arguments, dict):
        return ToolArgumentValidation(
            is_valid=False,
            error_type=FailureType.INVALID_FORMAT.value,
            error_message=(
                "Invalid tool arguments format; expected a JSON object, "
                f"got {type(raw_arguments).__name__}."
            ),
        )

    return ToolArgumentValidation(is_valid=True, arguments=raw_arguments)


def validate_tool_arguments(tool: Any, raw_arguments: Any) -> ToolArgumentValidation:
    """Normalize arguments and validate them against a LightClaw BaseTool schema."""
    normalized = normalize_tool_arguments(raw_arguments)
    if not normalized.is_valid:
        return normalized

    is_valid, error_message = tool.validate_args(normalized.arguments)
    if not is_valid:
        return ToolArgumentValidation(
            is_valid=False,
            arguments=normalized.arguments,
            error_type=FailureType.WRONG_ARGS.value,
            error_message=error_message or "Tool arguments failed schema validation.",
        )

    return normalized
