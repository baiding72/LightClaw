import json

from app.training.spa import (
    action_validity,
    build_spa_rollout,
    prepare_spa_training_data,
    redistribute_progress,
)


def test_spa_progress_scores_sum_to_final_reward() -> None:
    actions = [
        {"step_id": "t:1", "trace_id": "t", "action_type": "tool_call", "status": "success"},
        {"step_id": "t:2", "trace_id": "t", "action_type": "tool_call", "status": "failed", "error_type": "wrong_args"},
        {"step_id": "t:3", "trace_id": "t", "action_type": "tool_call", "status": "success"},
    ]

    scores = redistribute_progress(actions, 1.0)

    assert scores == [0.5, 0.0, 0.5]
    assert sum(scores) == 1.0


def test_safe_stop_counts_as_valid_positive_behavior() -> None:
    action = {"status": "blocked", "stop_reason": "login_required"}

    assert action_validity(action) == 1.0

    rollout = build_spa_rollout(
        task_id="task",
        prompt="招聘 safe dry-run",
        source="unit_test",
        actions=[{"step_id": "t:1", "trace_id": "t", "action_type": "tool_call", "status": "blocked", "stop_reason": "login_required"}],
    )

    assert rollout.final_reward == 1.0
    assert rollout.steps[0].progress_score == 1.0
    assert "safe_stop_is_positive_behavior" in rollout.steps[0].reward_notes


def test_spa_keeps_cumulative_constraint_for_partial_failed_candidate() -> None:
    actions = [
        {"step_id": "t:1", "trace_id": "t", "action_type": "tool_call", "status": "failed", "error_type": "wrong_args"},
        {"step_id": "t:2", "trace_id": "t", "action_type": "tool_call", "status": "failed", "error_type": "wrong_tool"},
    ]

    scores = redistribute_progress(actions, 0.4)

    assert scores == [0.2, 0.2]
    assert sum(scores) == 0.4


def test_prepare_spa_training_data_outputs_files(tmp_path) -> None:
    input_dir = tmp_path / "exports"
    input_dir.mkdir()
    (input_dir / "sft.jsonl").write_text(
        json.dumps({
            "messages": [
                {"role": "system", "content": "s"},
                {"role": "user", "content": "u"},
                {"role": "assistant", "content": json.dumps([
                    {"step_id": "r:1", "trace_id": "r", "action_type": "tool_call", "status": "success"},
                    {"step_id": "r:2", "trace_id": "r", "action_type": "tool_call", "status": "blocked", "stop_reason": "safe_stop"},
                ])},
            ],
            "metadata": {"task_id": "recruiting", "source": "trajectory", "sample_type": "recruiting_safe_stop"},
        }) + "\n",
        encoding="utf-8",
    )
    (input_dir / "grpo.jsonl").write_text(
        json.dumps({
            "prompt": "p",
            "candidate_trajectories": [
                {"label": "chosen", "actions": [{"step_id": "g:1", "trace_id": "g", "action_type": "tool_call", "status": "success"}], "final_score": 0.8},
            ],
            "metadata": {"task_id": "grpo_task", "source": "fixture"},
        }) + "\n",
        encoding="utf-8",
    )

    result = prepare_spa_training_data(input_dir, tmp_path / "spa")

    assert result["files"]["spa_rollouts"]["count"] == 2
    assert result["files"]["progress_attribution"]["count"] == 3
    assert (tmp_path / "spa" / "ppo_ready.jsonl").exists()
    card = result["files"]["spa_data_card"]
    assert card["training_status"] == "data_preparation_only_no_model_training"
    assert card["safe_stop_step_count"] == 1
