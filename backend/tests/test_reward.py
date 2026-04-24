from app.core.enums import FailureType
from app.eval.reward import ExpectedAction, RuleBasedVerifier
from app.schemas.action import AgentAction, AgentActionType


def test_reward_scores_successful_tool_use() -> None:
    action = AgentAction(
        action_type=AgentActionType.TOOL_CALL,
        step_id="s1",
        trace_id="t1",
        tool_name="add_todo",
        arguments={"title": "复查简历"},
        status="success",
        latency_ms=10,
    )
    reward = RuleBasedVerifier().score(
        [action],
        expected_actions=[ExpectedAction(tool_name="add_todo", arguments={"title": "复查简历"})],
        task_success=True,
    )

    assert reward.task_success == 1.0
    assert reward.tool_name_correct == 1.0
    assert reward.argument_correct == 1.0
    assert reward.final_score > 0.9


def test_reward_tracks_self_correction_recovery() -> None:
    failed = AgentAction(
        action_type=AgentActionType.TOOL_CALL,
        step_id="s1",
        trace_id="t1",
        tool_name="write_note",
        arguments={"title": "总结"},
        status="failed",
        error_type=FailureType.WRONG_ARGS.value,
        error_message="Missing required parameter: content",
    )
    repaired = AgentAction(
        action_type=AgentActionType.SELF_CORRECTION,
        step_id="s2",
        trace_id="t1",
        tool_name="write_note",
        arguments={"title": "总结", "content": "已补齐"},
        status="success",
    )

    reward = RuleBasedVerifier().score([failed, repaired], task_success=True)

    assert reward.recovery_success == 1.0
    assert reward.format_valid == 1.0


def test_reward_penalizes_policy_violation() -> None:
    action = AgentAction(
        action_type=AgentActionType.TOOL_CALL,
        step_id="s1",
        trace_id="t1",
        tool_name="dangerous",
        arguments={},
        status="failed",
        error_type=FailureType.POLICY_VIOLATION.value,
        error_message="blocked",
    )
    reward = RuleBasedVerifier().score([action], task_success=False)

    assert reward.policy_violation_penalty == 1.0
    assert reward.final_score == 0.0
