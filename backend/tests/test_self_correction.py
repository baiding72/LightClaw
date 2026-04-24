from app.eval.deterministic import build_demo_action_trajectories
from app.training.self_correction import (
    calculate_self_correction_metrics,
    construct_self_correction_samples,
)


def test_self_correction_sample_construction_covers_wrong_args() -> None:
    samples = construct_self_correction_samples(build_demo_action_trajectories())
    wrong_args = [sample for sample in samples if sample.error_type == "wrong_args"]

    assert wrong_args
    assert wrong_args[0].attempt_action["status"] == "failed"
    assert wrong_args[0].revision_action["status"] == "success"
    assert wrong_args[0].recovery_success is True


def test_over_correction_detection() -> None:
    samples = construct_self_correction_samples(build_demo_action_trajectories())
    over_corrections = [sample for sample in samples if sample.over_correction]

    assert over_corrections
    assert over_corrections[0].error_type == "over_correction"
    assert over_corrections[0].recovery_success is False


def test_self_correction_metrics_include_recovery_rate() -> None:
    samples = construct_self_correction_samples(build_demo_action_trajectories())
    metrics = calculate_self_correction_metrics(samples, total_tasks=7)

    assert metrics["correction_attempt_rate"] > 0
    assert metrics["recovery_success_rate"] > 0
    assert metrics["over_correction_rate"] > 0
    assert "wrong_args" in metrics["first_error_type_distribution"]
