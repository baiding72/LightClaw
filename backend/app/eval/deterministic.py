"""Deterministic evaluation fixtures that do not require an LLM API key."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.core.enums import FailureType
from app.eval.reward import ExpectedAction, RuleBasedVerifier
from app.gui_grounding import (
    CandidateBox,
    GroundingInput,
    GroundingLabel,
    RuleBasedGroundingModule,
    gui_action_accuracy,
)
from app.schemas.action import AgentAction, AgentActionType
from app.schemas.eval import EvaluationMetrics, EvaluationResponse, TaskEvaluationDetail


def build_demo_action_trajectories() -> list[dict[str, Any]]:
    """Return small deterministic trajectories covering success, repair and GUI grounding."""
    trace_success = "fixture_tool_success"
    trace_repair = "fixture_self_correction"
    trace_gui = "fixture_gui_grounding"
    return [
        {
            "task_id": "fixture_tool_use_success",
            "instruction": "创建一个待办：明天复查简历。",
            "expected_actions": [
                {"tool_name": "add_todo", "arguments": {"title": "明天复查简历"}}
            ],
            "task_success": True,
            "actions": [
                AgentAction(
                    action_type=AgentActionType.TOOL_CALL,
                    step_id="fixture_tool_success:1",
                    trace_id=trace_success,
                    tool_name="add_todo",
                    action_name="add_todo",
                    arguments={"title": "明天复查简历", "priority": "medium"},
                    status="success",
                    observation={"todo_id": 1, "message": "待办事项创建成功"},
                    latency_ms=12,
                ).model_dump(mode="json"),
            ],
        },
        {
            "task_id": "fixture_wrong_args_repair",
            "instruction": "写一条笔记，标题是投递总结，内容是已投递 2 个岗位。",
            "expected_actions": [
                {"tool_name": "write_note", "arguments": {"title": "投递总结", "content": "已投递 2 个岗位"}}
            ],
            "task_success": True,
            "actions": [
                AgentAction(
                    action_type=AgentActionType.TOOL_CALL,
                    step_id="fixture_self_correction:1",
                    trace_id=trace_repair,
                    tool_name="write_note",
                    action_name="write_note",
                    arguments={"title": "投递总结"},
                    status="failed",
                    error_type=FailureType.WRONG_ARGS.value,
                    error_message="Missing required parameter: content",
                    latency_ms=5,
                ).model_dump(mode="json"),
                AgentAction(
                    action_type=AgentActionType.SELF_CORRECTION,
                    step_id="fixture_self_correction:2",
                    trace_id=trace_repair,
                    tool_name="write_note",
                    action_name="write_note",
                    arguments={"title": "投递总结", "content": "已投递 2 个岗位"},
                    status="success",
                    observation={"note_id": 2, "message": "笔记创建成功"},
                    latency_ms=8,
                    metadata={"feedback": "content 参数缺失，按 verifier feedback 补齐。"},
                ).model_dump(mode="json"),
            ],
        },
        {
            "task_id": "fixture_gui_grounding_click",
            "instruction": "点击保存按钮。",
            "expected_actions": [],
            "task_success": True,
            "actions": [
                AgentAction(
                    action_type=AgentActionType.GUI_GROUNDING,
                    step_id="fixture_gui_grounding:1",
                    trace_id=trace_gui,
                    action_name="ground_selector",
                    arguments={"instruction": "点击保存按钮", "selector": "#save"},
                    status="success",
                    observation={"point": [120, 220], "bbox": [80, 200, 160, 240]},
                    latency_ms=3,
                ).model_dump(mode="json"),
            ],
        },
    ]


def run_grounding_fixture() -> float:
    module = RuleBasedGroundingModule()
    request = GroundingInput(
        instruction="点击保存按钮",
        candidates=[
            CandidateBox(candidate_id="cancel", selector="#cancel", text="取消", role="button", bbox=(10, 200, 70, 240)),
            CandidateBox(candidate_id="save", selector="#save", text="保存", role="button", bbox=(80, 200, 160, 240)),
        ],
    )
    prediction = module.predict(request)
    label = GroundingLabel(candidate_id="save", selector="#save", bbox=(80, 200, 160, 240))
    return gui_action_accuracy([prediction], [label])


def build_deterministic_evaluation(eval_name: str) -> EvaluationResponse:
    verifier = RuleBasedVerifier()
    fixtures = build_demo_action_trajectories()
    details: list[TaskEvaluationDetail] = []
    all_actions: list[dict[str, Any]] = []
    task_successes = 0
    total_latency = 0

    for item in fixtures:
        reward = verifier.score(
            item["actions"],
            expected_actions=[ExpectedAction.model_validate(a) for a in item.get("expected_actions", [])],
            task_success=item.get("task_success"),
        )
        actions = item["actions"]
        failures = [a.get("error_type") for a in actions if a.get("error_type")]
        is_success = reward.task_success == 1.0
        task_successes += 1 if is_success else 0
        latency = sum(int(a.get("latency_ms") or 0) for a in actions)
        total_latency += latency
        all_actions.extend(actions)
        details.append(
            TaskEvaluationDetail(
                task_id=item["task_id"],
                instruction=item["instruction"],
                is_success=is_success,
                steps_count=len(actions),
                tool_calls_count=sum(1 for a in actions if a.get("action_type") in {"tool_call", "self_correction"}),
                gui_actions_count=sum(1 for a in actions if str(a.get("action_type", "")).startswith("gui_")),
                failure_types=[f for f in failures if f],
                recovery_attempts=sum(1 for a in actions if a.get("status") == "failed"),
                successful_recoveries=sum(1 for a in actions if a.get("action_type") == "self_correction" and a.get("status") == "success"),
                latency_ms=latency,
                token_usage={"total": 0},
            )
        )

    total_actions = max(len(all_actions), 1)
    failed_actions = [a for a in all_actions if a.get("status") == "failed"]
    wrong_args = [a for a in all_actions if a.get("error_type") == FailureType.WRONG_ARGS.value]
    invalid_format = [a for a in all_actions if a.get("error_type") == FailureType.INVALID_FORMAT.value]
    policy_violations = [a for a in all_actions if a.get("error_type") == FailureType.POLICY_VIOLATION.value]
    recovery_attempts = sum(d.recovery_attempts for d in details)
    recoveries = sum(d.successful_recoveries for d in details)

    metrics = EvaluationMetrics(
        task_success_rate=task_successes / len(fixtures),
        tool_execution_success_rate=(total_actions - len(failed_actions)) / total_actions,
        recovery_rate=recoveries / recovery_attempts if recovery_attempts else 1.0,
        gui_action_accuracy=run_grounding_fixture(),
        invalid_tool_call_rate=len(invalid_format) / total_actions,
        wrong_args_rate=len(wrong_args) / total_actions,
        policy_violation_rate=len(policy_violations) / total_actions,
        avg_steps=sum(d.steps_count for d in details) / len(details),
        avg_latency_ms=total_latency / len(details),
        total_token_cost=0.0,
    )
    return EvaluationResponse(
        eval_id=f"eval_{uuid.uuid4().hex[:8]}",
        eval_name=eval_name,
        total_tasks=len(fixtures),
        metrics=metrics,
        details=details,
        created_at=datetime.now(),
    )
