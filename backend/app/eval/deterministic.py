"""Deterministic evaluation fixtures that do not require an LLM API key."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.enums import FailureType
from app.eval.reward import ExpectedAction, RuleBasedVerifier
from app.gui_grounding import (
    CandidateBox,
    GroundingInput,
    GroundingLabel,
    RuleBasedGroundingModule,
    gui_action_accuracy,
)
from app.recruiting.eval import calculate_recruiting_metrics
from app.runtime.skill_selector import SkillSelector
from app.schemas.action import AgentAction, AgentActionType
from app.schemas.eval import EvaluationMetrics, EvaluationResponse, TaskEvaluationDetail
from app.tools.registry import ToolRegistry
from app.tools.skills import build_default_tool_skills
from app.training.self_correction import (
    calculate_self_correction_metrics,
    construct_self_correction_samples,
)


def build_demo_action_trajectories() -> list[dict[str, Any]]:
    """Return small deterministic trajectories covering success, repair and GUI grounding."""
    trace_success = "fixture_tool_success"
    trace_repair = "fixture_self_correction"
    trace_gui = "fixture_gui_grounding"
    trace_wrong_tool = "fixture_wrong_tool"
    trace_invalid = "fixture_invalid_format"
    trace_policy = "fixture_policy_violation"
    trace_gui_miss = "fixture_gui_click_miss"
    trace_over = "fixture_over_correction"
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
        {
            "task_id": "fixture_wrong_tool_repair",
            "instruction": "写一条笔记，标题是求职复盘，内容是今天跟进 3 家公司。",
            "expected_actions": [
                {"tool_name": "write_note", "arguments": {"title": "求职复盘", "content": "今天跟进 3 家公司"}}
            ],
            "task_success": True,
            "actions": [
                AgentAction(
                    action_type=AgentActionType.TOOL_CALL,
                    step_id="fixture_wrong_tool:1",
                    trace_id=trace_wrong_tool,
                    tool_name="add_todo",
                    action_name="add_todo",
                    arguments={"title": "求职复盘"},
                    status="failed",
                    error_type=FailureType.WRONG_TOOL.value,
                    error_message="Verifier: task requires a note artifact, not a todo.",
                    metadata={"verifier_feedback": "应使用 write_note 保存内容，而不是 add_todo。"},
                    latency_ms=4,
                ).model_dump(mode="json"),
                AgentAction(
                    action_type=AgentActionType.SELF_CORRECTION,
                    step_id="fixture_wrong_tool:2",
                    trace_id=trace_wrong_tool,
                    tool_name="write_note",
                    action_name="write_note",
                    arguments={"title": "求职复盘", "content": "今天跟进 3 家公司"},
                    status="success",
                    observation={"note_id": 3},
                    metadata={"feedback": "根据 verifier feedback 改用 write_note 并补齐 content。"},
                    latency_ms=7,
                ).model_dump(mode="json"),
            ],
        },
        {
            "task_id": "fixture_invalid_format_repair",
            "instruction": "创建待办：明早 9 点查看笔试通知。",
            "expected_actions": [
                {"tool_name": "add_todo", "arguments": {"title": "明早 9 点查看笔试通知"}}
            ],
            "task_success": True,
            "actions": [
                AgentAction(
                    action_type=AgentActionType.TOOL_CALL,
                    step_id="fixture_invalid_format:1",
                    trace_id=trace_invalid,
                    tool_name="add_todo",
                    action_name="add_todo",
                    arguments={},
                    status="failed",
                    error_type=FailureType.INVALID_FORMAT.value,
                    error_message="Invalid JSON tool arguments: expected object.",
                    metadata={"verifier_feedback": "工具参数必须是 JSON object，并包含 title。"},
                    latency_ms=2,
                ).model_dump(mode="json"),
                AgentAction(
                    action_type=AgentActionType.SELF_CORRECTION,
                    step_id="fixture_invalid_format:2",
                    trace_id=trace_invalid,
                    tool_name="add_todo",
                    action_name="add_todo",
                    arguments={"title": "明早 9 点查看笔试通知", "priority": "high"},
                    status="success",
                    observation={"todo_id": 4},
                    metadata={"feedback": "将非法格式修正为合法 JSON object。"},
                    latency_ms=6,
                ).model_dump(mode="json"),
            ],
        },
        {
            "task_id": "fixture_policy_violation_repair",
            "instruction": "在没有选中目标标签页时读取当前招聘页面。",
            "expected_actions": [],
            "task_success": True,
            "actions": [
                AgentAction(
                    action_type=AgentActionType.GUI_CLICK,
                    step_id="fixture_policy_violation:1",
                    trace_id=trace_policy,
                    action_name="click",
                    arguments={"selector": ".apply"},
                    status="failed",
                    error_type=FailureType.POLICY_VIOLATION.value,
                    error_message="No target browser tab selected.",
                    metadata={"verifier_feedback": "No Target, No Run；应请求用户选择目标标签页。"},
                    latency_ms=3,
                ).model_dump(mode="json"),
                AgentAction(
                    action_type=AgentActionType.ASK_USER,
                    step_id="fixture_policy_violation:2",
                    trace_id=trace_policy,
                    action_name="ask_user",
                    arguments={"question": "请选择要操作的目标网页标签页。"},
                    status="success",
                    observation={"checkpoint": "target_tab_required"},
                    metadata={"feedback": "策略违规后转为用户确认 checkpoint。"},
                    latency_ms=1,
                ).model_dump(mode="json"),
            ],
        },
        {
            "task_id": "fixture_gui_click_miss_repair",
            "instruction": "点击页面上的保存按钮。",
            "expected_actions": [],
            "task_success": True,
            "actions": [
                AgentAction(
                    action_type=AgentActionType.GUI_CLICK,
                    step_id="fixture_gui_click_miss:1",
                    trace_id=trace_gui_miss,
                    action_name="click",
                    arguments={"point": [20, 20], "selector": "#cancel"},
                    status="failed",
                    error_type=FailureType.GUI_CLICK_MISS.value,
                    error_message="Point missed target bbox for 保存 button.",
                    metadata={"verifier_feedback": "目标保存按钮 bbox=[80,200,160,240]。"},
                    latency_ms=5,
                ).model_dump(mode="json"),
                AgentAction(
                    action_type=AgentActionType.GUI_GROUNDING,
                    step_id="fixture_gui_click_miss:2",
                    trace_id=trace_gui_miss,
                    action_name="ground_selector",
                    arguments={"point": [120, 220], "bbox": [80, 200, 160, 240], "selector": "#save"},
                    status="success",
                    observation={"hit": True},
                    metadata={"feedback": "基于 bbox feedback 将点击点修正到保存按钮中心。"},
                    latency_ms=4,
                ).model_dump(mode="json"),
            ],
        },
        {
            "task_id": "fixture_over_correction",
            "instruction": "创建待办：今晚更新简历。",
            "expected_actions": [
                {"tool_name": "add_todo", "arguments": {"title": "今晚更新简历"}}
            ],
            "task_success": False,
            "actions": [
                AgentAction(
                    action_type=AgentActionType.TOOL_CALL,
                    step_id="fixture_over_correction:1",
                    trace_id=trace_over,
                    tool_name="add_todo",
                    action_name="add_todo",
                    arguments={"title": "今晚更新简历"},
                    status="success",
                    observation={"todo_id": 5},
                    metadata={"verifier_feedback": "原 action 已正确，不需要修正。"},
                    latency_ms=5,
                ).model_dump(mode="json"),
                AgentAction(
                    action_type=AgentActionType.SELF_CORRECTION,
                    step_id="fixture_over_correction:2",
                    trace_id=trace_over,
                    tool_name="write_note",
                    action_name="write_note",
                    arguments={"title": "今晚更新简历", "content": "错误地改成笔记"},
                    status="success",
                    error_type=FailureType.OVER_CORRECTION.value,
                    observation={"note_id": 6},
                    metadata={"feedback": "错误修改了已经正确的 add_todo action。"},
                    latency_ms=5,
                ).model_dump(mode="json"),
            ],
        },
    ]


FAILURE_TYPES_FOR_REPORT = [
    FailureType.INVALID_FORMAT.value,
    FailureType.WRONG_TOOL.value,
    FailureType.WRONG_ARGS.value,
    FailureType.TOOL_TIMEOUT.value,
    FailureType.TOOL_EXCEPTION.value,
    FailureType.POLICY_VIOLATION.value,
    FailureType.REDUNDANT_TOOL_CALL.value,
    FailureType.GUI_CLICK_MISS.value,
    FailureType.HALLUCINATED_OBSERVATION.value,
    FailureType.OVER_CORRECTION.value,
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
    self_correction_samples = construct_self_correction_samples(fixtures)
    self_correction_metrics = calculate_self_correction_metrics(
        self_correction_samples,
        total_tasks=len(fixtures),
    )
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
        self_correction_metrics=self_correction_metrics,
        failure_analysis=build_failure_analysis(fixtures),
        recruiting_metrics=_load_recruiting_metrics(),
        skill_metrics=build_skill_metrics(fixtures),
        created_at=datetime.now(),
    )


def build_skill_metrics(trajectories: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate progressive skill selection on deterministic task instructions."""
    registry = ToolRegistry()
    for skill in build_default_tool_skills():
        registry.register_skill(skill)

    selector = SkillSelector(registry)
    selections: list[dict[str, Any]] = []
    skill_distribution: dict[str, int] = {}
    loaded_tool_counts: list[int] = []

    for item in trajectories:
        instruction = item.get("instruction", "")
        is_recruiting = any(keyword in instruction.lower() for keyword in ["招聘", "投递", "岗位", "申请", "resume", "job"])
        selection = selector.select(
            instruction,
            browser_context={"selected_tab": {"url": "https://fixture.local/careers"}} if is_recruiting else None,
            scenario_type="recruiting" if is_recruiting else None,
        )
        before = registry.get_loaded_tool_count()
        for skill_id in selection.selected_skills:
            registry.load_skill(skill_id)
            skill_distribution[skill_id] = skill_distribution.get(skill_id, 0) + 1
        after = registry.get_loaded_tool_count()
        loaded_tool_counts.append(after - before)
        selections.append({
            "task_id": item.get("task_id"),
            "selected_skills": selection.selected_skills,
            "allowed_tools_count": len(selection.allowed_tools),
            "newly_loaded_tools": after - before,
        })

    return {
        "registered_skill_count": len(registry.list_skills()),
        "loaded_tool_count": registry.get_loaded_tool_count(),
        "avg_selected_skills": (
            sum(len(selection["selected_skills"]) for selection in selections) / len(selections)
            if selections else 0.0
        ),
        "avg_newly_loaded_tools": sum(loaded_tool_counts) / len(loaded_tool_counts) if loaded_tool_counts else 0.0,
        "skill_distribution": skill_distribution,
        "sample_selections": selections[:5],
    }


def build_failure_analysis(trajectories: list[dict[str, Any]]) -> dict[str, Any]:
    verifier = RuleBasedVerifier()
    all_failures: list[dict[str, Any]] = []
    for item in trajectories:
        actions = item.get("actions", [])
        reward = verifier.score(
            actions,
            expected_actions=item.get("expected_actions", []),
            task_success=item.get("task_success"),
        )
        for action in actions:
            error_type = action.get("error_type")
            if not error_type:
                continue
            all_failures.append({
                "error_type": error_type,
                "task_id": item.get("task_id"),
                "trace_id": action.get("trace_id"),
                "actions": actions,
                "reward_breakdown": reward.model_dump(),
                "failure_reason": action.get("error_message")
                or action.get("metadata", {}).get("feedback")
                or error_type,
            })

    total = max(len(all_failures), 1)
    by_type: dict[str, dict[str, Any]] = {}
    for error_type in FAILURE_TYPES_FOR_REPORT:
        cases = [failure for failure in all_failures if failure["error_type"] == error_type]
        by_type[error_type] = {
            "count": len(cases),
            "percentage": len(cases) / total if all_failures else 0.0,
            "sample_cases": cases[:3],
        }
    return {"total_failures": len(all_failures), "by_error_type": by_type}


def get_fixture_case(case_id: str) -> dict[str, Any] | None:
    for item in build_demo_action_trajectories():
        if item.get("task_id") == case_id or case_id in item.get("task_id", ""):
            return item
    return None


def _load_recruiting_metrics() -> dict[str, Any]:
    configured = Path(get_settings().trajectories_dir) / "recruiting" / "latest"
    repo_backend = Path(__file__).resolve().parents[2] / "data" / "trajectories" / "recruiting" / "latest"
    output_dir = repo_backend if repo_backend.exists() else configured
    if not output_dir.exists():
        return {
            "jobs_extracted_count": 0,
            "apply_flow_steps_count": 0,
            "blocked_by_login": False,
            "blocked_by_captcha": False,
            "safe_stop_count": 0,
            "stop_reason_distribution": {},
            "safe_stop_rate": 0.0,
            "extraction_schema_pass_rate": 0.0,
        }
    return calculate_recruiting_metrics(output_dir)
