from app.eval.deterministic import (
    build_demo_action_trajectories,
    build_deterministic_evaluation,
    build_failure_analysis,
)
from app.training.replay import render_replay


def test_eval_report_contains_self_correction_and_failure_analysis() -> None:
    report = build_deterministic_evaluation("test_eval")

    assert report.self_correction_metrics["recovery_success_rate"] > 0
    assert report.failure_analysis["total_failures"] > 0
    assert "wrong_args" in report.failure_analysis["by_error_type"]
    assert report.failure_analysis["by_error_type"]["wrong_args"]["sample_cases"]


def test_failure_analysis_keeps_sample_cases() -> None:
    analysis = build_failure_analysis(build_demo_action_trajectories())
    case = analysis["by_error_type"]["gui_click_miss"]["sample_cases"][0]

    assert case["task_id"] == "fixture_gui_click_miss_repair"
    assert case["actions"]
    assert "reward_breakdown" in case


def test_replay_fixture_output_does_not_error() -> None:
    case = [
        item for item in build_demo_action_trajectories()
        if item["task_id"] == "fixture_wrong_args_repair"
    ][0]
    output = render_replay(case)

    assert "Replay: fixture_wrong_args_repair" in output
    assert "Reward change" in output
