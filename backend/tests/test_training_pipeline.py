import json

from app.training.distillation import distill_trajectories
from app.training.pipeline import run_training_pipeline


def test_distill_trajectories_compacts_agent_actions(tmp_path) -> None:
    trajectory_dir = tmp_path / "trajectories"
    trajectory_dir.mkdir()
    (trajectory_dir / "trace.jsonl").write_text(
        json.dumps({
            "action_type": "tool_call",
            "step_id": "t:1",
            "trace_id": "t",
            "tool_name": "recruiting_browser",
            "action_name": "extract_apply_flow",
            "arguments": {"action": "extract_apply_flow"},
            "status": "blocked",
            "stop_reason": "login_required",
            "dom_snapshot": "x" * 2000,
        }) + "\n",
        encoding="utf-8",
    )

    result = distill_trajectories(trajectory_dir=trajectory_dir, output_dir=tmp_path / "distilled")

    assert result["files"]["distilled_trajectories"]["count"] == 1
    row = json.loads((tmp_path / "distilled" / "distilled_trajectories.jsonl").read_text(encoding="utf-8"))
    assert row["sample_type"] == "recruiting_safe_stop"
    assert row["quality_score"] == 1.0
    assert row["actions"][0]["dom_truncated"] is True


def test_training_pipeline_runs_all_stages(tmp_path) -> None:
    result = run_training_pipeline(output_root=tmp_path / "pipeline")

    assert result["status"] == "passed"
    assert result["training_status"] == "data_preparation_only_no_model_training"
    assert [stage["name"] for stage in result["stages"]] == [
        "trajectory_collection",
        "trajectory_distillation",
        "sft_dpo_grpo_export",
        "spa_rl_preparation",
        "evaluation",
    ]
    assert (tmp_path / "pipeline" / "training_pipeline_report.json").exists()
    assert result["stages"][3]["output"]["files"]["ppo_ready"]["count"] > 0
