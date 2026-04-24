"""
Rule-based verifier and reward scoring for deterministic LightClaw demos.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import FailureType
from app.schemas.action import AgentAction, AgentActionStatus


class RewardBreakdown(BaseModel):
    task_success: float = 0.0
    tool_name_correct: float = 0.0
    argument_correct: float = 0.0
    format_valid: float = 0.0
    recovery_success: float = 0.0
    gui_grounding_hit: float = 0.0
    redundant_tool_call_penalty: float = 0.0
    policy_violation_penalty: float = 0.0
    latency_cost_proxy: float = 0.0
    final_score: float = 0.0


class ExpectedAction(BaseModel):
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    gui_target_id: str | None = None


def _coerce_actions(actions: Iterable[AgentAction | dict[str, Any]]) -> list[AgentAction]:
    coerced: list[AgentAction] = []
    for action in actions:
        if isinstance(action, AgentAction):
            coerced.append(action)
        else:
            coerced.append(AgentAction.model_validate(action))
    return coerced


class RuleBasedVerifier:
    """Small deterministic verifier for demos, tests and reward export."""

    def score(
        self,
        actions: Iterable[AgentAction | dict[str, Any]],
        *,
        expected_actions: list[ExpectedAction | dict[str, Any]] | None = None,
        task_success: bool | None = None,
    ) -> RewardBreakdown:
        normalized = _coerce_actions(actions)
        expected = [
            item if isinstance(item, ExpectedAction) else ExpectedAction.model_validate(item)
            for item in (expected_actions or [])
        ]

        successful = [a for a in normalized if a.status == AgentActionStatus.SUCCESS.value]
        failed = [a for a in normalized if a.status == AgentActionStatus.FAILED.value]
        total = max(len(normalized), 1)

        wrong_args = [
            a for a in normalized
            if a.error_type in {FailureType.WRONG_ARGS.value, FailureType.INVALID_FORMAT.value}
        ]
        policy_violations = [
            a for a in normalized if a.error_type == FailureType.POLICY_VIOLATION.value
        ]
        redundant = [
            a for a in normalized if a.error_type == FailureType.REDUNDANT_TOOL_CALL.value
        ]

        tool_name_correct = 1.0
        argument_correct = 1.0
        if expected:
            name_hits = 0
            arg_hits = 0
            for expected_action in expected:
                candidates = [
                    a for a in normalized
                    if expected_action.tool_name is None or a.tool_name == expected_action.tool_name
                ]
                if candidates:
                    name_hits += 1
                if any(
                    all(a.arguments.get(k) == v for k, v in expected_action.arguments.items())
                    for a in candidates
                ):
                    arg_hits += 1
            tool_name_correct = name_hits / len(expected)
            argument_correct = arg_hits / len(expected)
        elif wrong_args:
            argument_correct = 1.0 - (len(wrong_args) / total)

        has_repair = any(a.action_type == "self_correction" for a in successful)
        recovery_success = 1.0 if failed and has_repair else (1.0 if not failed else 0.0)
        gui_actions = [a for a in normalized if a.action_type in {"gui_click", "gui_grounding"}]
        gui_hits = [a for a in gui_actions if a.status == AgentActionStatus.SUCCESS.value]
        gui_grounding_hit = len(gui_hits) / len(gui_actions) if gui_actions else 1.0
        latency_ms = sum((a.latency_ms or 0) for a in normalized)
        latency_cost_proxy = max(0.0, min(1.0, 1.0 - (latency_ms / 30_000)))

        inferred_task_success = task_success
        if inferred_task_success is None:
            inferred_task_success = bool(successful) and not policy_violations

        breakdown = RewardBreakdown(
            task_success=1.0 if inferred_task_success else 0.0,
            tool_name_correct=tool_name_correct,
            argument_correct=argument_correct,
            format_valid=0.0 if any(a.error_type == FailureType.INVALID_FORMAT.value for a in normalized) else 1.0,
            recovery_success=recovery_success,
            gui_grounding_hit=gui_grounding_hit,
            redundant_tool_call_penalty=len(redundant) / total,
            policy_violation_penalty=len(policy_violations) / total,
            latency_cost_proxy=latency_cost_proxy,
        )
        positive = (
            breakdown.task_success
            + breakdown.tool_name_correct
            + breakdown.argument_correct
            + breakdown.format_valid
            + breakdown.recovery_success
            + breakdown.gui_grounding_hit
            + breakdown.latency_cost_proxy
        ) / 7
        penalty = min(1.0, breakdown.redundant_tool_call_penalty + breakdown.policy_violation_penalty)
        breakdown.final_score = max(0.0, positive - penalty)
        return breakdown
