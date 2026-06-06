"""Structured tool execution results for the agent harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


FAILURE_MARKERS = ("error", "failed", "denied", "paused by policy", "missing required")
UNCHANGED_MARKERS = ("unchanged", "already exists", "not found")
SUCCESS_MARKERS = ("saved", "updated", "wrote", "created", "deleted", "cleared", "success")


@dataclass(frozen=True)
class ToolExecutionResult:
    tool_name: str
    ok: bool
    status: str
    output: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_observation(self) -> str:
        return self.output

    def to_trace(self) -> dict[str, Any]:
        return {
            "tool_ok": self.ok,
            "tool_status": self.status,
            "tool_output": self.output,
            "tool_metadata": self.metadata,
        }


def classify_tool_output(tool_name: str, output: Any, *, denied: bool = False) -> ToolExecutionResult:
    text = "" if output is None else str(output)
    lowered = text.lower()
    if denied:
        return ToolExecutionResult(tool_name=tool_name, ok=False, status="denied", output=text)
    if any(marker in lowered for marker in FAILURE_MARKERS):
        return ToolExecutionResult(tool_name=tool_name, ok=False, status="error", output=text)
    if any(marker in lowered for marker in UNCHANGED_MARKERS):
        return ToolExecutionResult(tool_name=tool_name, ok=False, status="unchanged", output=text)
    if any(marker in lowered for marker in SUCCESS_MARKERS):
        return ToolExecutionResult(tool_name=tool_name, ok=True, status="updated", output=text)
    return ToolExecutionResult(tool_name=tool_name, ok=True, status="ok", output=text)
