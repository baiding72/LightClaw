import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_script_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


run_all_checks_module = load_script_module("run_all_checks_script", "scripts/run_all_checks.py")
train_stub_module = load_script_module("train_stub_script", "scripts/train_stub.py")
run_showcase_module = load_script_module("run_showcase_script", "scripts/run_showcase.py")
run_all_checks = run_all_checks_module.run_all_checks
dry_run = train_stub_module.dry_run
build_showcase = run_showcase_module.build_showcase


def test_run_all_checks_smoke_with_mocked_subprocess(monkeypatch, tmp_path) -> None:
    def fake_run(command, cwd, check, text, capture_output):  # noqa: ANN001
        del cwd, check, text, capture_output
        stdout = "# replay" if "replay_trace.py" in command else "{}"
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(run_all_checks_module, "DEFAULT_EXPORT_DIR", tmp_path / "exports")
    monkeypatch.setattr(run_all_checks_module, "DEFAULT_SPA_EXPORT_DIR", tmp_path / "spa")
    monkeypatch.setattr(run_all_checks_module, "DEFAULT_REPLAY_PATH", tmp_path / "replay.md")
    monkeypatch.setattr(run_all_checks_module, "DEFAULT_RECRUITING_REPLAY_PATH", tmp_path / "recruiting.md")
    monkeypatch.setattr(subprocess, "run", fake_run)

    summary = run_all_checks()

    assert summary["passed"] is True
    assert Path(summary["replay_output_path"]).exists()
    assert Path(summary["recruiting_replay_output_path"]).exists()
    assert len(summary["checks"]) == 7
    assert summary["spa_training_export_path"].endswith("spa")


def test_run_all_checks_reports_failure(monkeypatch, tmp_path) -> None:
    def fake_run(command, cwd, check, text, capture_output):  # noqa: ANN001
        del cwd, check, text, capture_output
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="boom")

    monkeypatch.setattr(run_all_checks_module, "DEFAULT_EXPORT_DIR", tmp_path / "exports")
    monkeypatch.setattr(run_all_checks_module, "DEFAULT_SPA_EXPORT_DIR", tmp_path / "spa")
    monkeypatch.setattr(run_all_checks_module, "DEFAULT_REPLAY_PATH", tmp_path / "replay.md")
    monkeypatch.setattr(run_all_checks_module, "DEFAULT_RECRUITING_REPLAY_PATH", tmp_path / "recruiting.md")
    monkeypatch.setattr(subprocess, "run", fake_run)

    summary = run_all_checks()

    assert summary["passed"] is False
    assert summary["checks"][0]["error"] == "exit_code=1"


def test_train_stub_dry_run(tmp_path) -> None:
    (tmp_path / "sft.jsonl").write_text(
        json.dumps({"messages": [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "dpo.jsonl").write_text(
        json.dumps({
            "system": "s",
            "prompt": "p",
            "chosen": json.dumps({"status": "success"}),
            "rejected": json.dumps({"status": "failed"}),
        }) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "grpo.jsonl").write_text(
        json.dumps({
            "prompt": "p",
            "candidate_trajectories": [
                {"actions": [], "reward_breakdown": {}, "final_score": 0.1},
                {"actions": [], "reward_breakdown": {}, "final_score": 0.9},
            ],
        }) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "self_correction.jsonl").write_text(
        json.dumps({
            "original_prompt": "p",
            "attempt_action": {},
            "error_type": "wrong_args",
            "final_status": "success",
            "trace_id": "t",
            "task_id": "task",
        }) + "\n",
        encoding="utf-8",
    )

    result = dry_run(tmp_path)

    assert result["ready"] is True
    assert result["message"] == "ready for SFT/DPO/GRPO training"
    assert result["counts"]["dpo"] == 1


def test_train_stub_validates_spa_dir(tmp_path) -> None:
    base_dir = tmp_path / "base"
    spa_dir = tmp_path / "spa"
    base_dir.mkdir()
    spa_dir.mkdir()
    (base_dir / "sft.jsonl").write_text(
        json.dumps({"messages": [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]}) + "\n",
        encoding="utf-8",
    )
    (base_dir / "dpo.jsonl").write_text(
        json.dumps({"system": "s", "prompt": "p", "chosen": "{}", "rejected": "{}"}) + "\n",
        encoding="utf-8",
    )
    (base_dir / "grpo.jsonl").write_text(
        json.dumps({
            "prompt": "p",
            "candidate_trajectories": [
                {"actions": [], "reward_breakdown": {}, "final_score": 0.1},
                {"actions": [], "reward_breakdown": {}, "final_score": 0.9},
            ],
        }) + "\n",
        encoding="utf-8",
    )
    (base_dir / "self_correction.jsonl").write_text(
        json.dumps({
            "original_prompt": "p",
            "attempt_action": {},
            "error_type": "wrong_args",
            "final_status": "success",
            "trace_id": "t",
            "task_id": "task",
        }) + "\n",
        encoding="utf-8",
    )
    step = {
        "step_id": "t:1",
        "trace_id": "t",
        "action_type": "tool_call",
        "progress_score": 1.0,
        "action_validity": 1.0,
        "dense_reward": 1.1,
    }
    (spa_dir / "spa_rollouts.jsonl").write_text(
        json.dumps({"task_id": "task", "trace_id": "t", "prompt": "p", "source": "unit", "final_reward": 1.0, "total_dense_reward": 1.1, "steps": [step]}) + "\n",
        encoding="utf-8",
    )
    (spa_dir / "progress_attribution.jsonl").write_text(json.dumps(step) + "\n", encoding="utf-8")
    (spa_dir / "ppo_ready.jsonl").write_text(
        json.dumps({"prompt": "p", "trajectory": [step], "dense_rewards": [1.1], "final_reward": 1.0}) + "\n",
        encoding="utf-8",
    )

    result = dry_run(base_dir, spa_dir)

    assert result["spa_counts"]["spa_rollouts"] == 1
    assert "SPA-style" in result["message"]


def test_run_showcase_builds_report(monkeypatch, tmp_path) -> None:
    eval_report = tmp_path / "latest.json"
    data_card = tmp_path / "data_card.json"
    spa_data_card = tmp_path / "spa_data_card.json"
    recruiting_replay = tmp_path / "recruiting.md"
    correction_replay = tmp_path / "wrong_args.md"
    eval_report.write_text(json.dumps({
        "recruiting_metrics": {"jobs_extracted_count": 2, "safe_stop_rate": 1.0},
        "skill_metrics": {"registered_skill_count": 5, "loaded_tool_count": 12},
    }), encoding="utf-8")
    data_card.write_text(json.dumps({
        "source": "fixture",
        "sft_count": 1,
        "dpo_pair_count": 1,
        "grpo_group_count": 1,
        "self_correction_count": 1,
        "schema_validation_pass_rate": 1.0,
        "invalid_sample_count": 0,
        "sample_type_distribution": {"recruiting_safe_stop": 1},
    }), encoding="utf-8")
    spa_data_card.write_text(json.dumps({
        "rollout_count": 3,
        "step_count": 7,
        "avg_action_validity": 1.0,
        "reward_design": "dense_reward = stepwise_progress + 0.1 * action_validity",
    }), encoding="utf-8")
    recruiting_replay.write_text("# recruiting", encoding="utf-8")
    correction_replay.write_text("# correction", encoding="utf-8")

    def fake_run_all_checks(with_pytest=False):  # noqa: ANN001, ARG001
        return {
            "passed": True,
            "eval_report_path": str(eval_report),
            "data_card_path": str(data_card),
            "spa_data_card_path": str(spa_data_card),
            "recruiting_replay_output_path": str(recruiting_replay),
            "replay_output_path": str(correction_replay),
            "training_export_path": str(tmp_path / "exports"),
            "spa_training_export_path": str(tmp_path / "spa"),
            "recruiting_trace_path": str(tmp_path / "traces.jsonl"),
            "checks": [],
        }

    monkeypatch.setattr(run_showcase_module, "run_all_checks", fake_run_all_checks)

    result = build_showcase(output_dir=tmp_path / "showcase")

    assert result["passed"] is True
    assert result["summary"]["p0_recruiting_safe_dry_run"]["metrics"]["jobs_extracted_count"] == 2
    assert result["summary"]["p1_skill_progressive_loading"]["metrics"]["loaded_tool_count"] == 12
    assert result["summary"]["p3_spa_training_preparation"]["spa_data_card"]["rollout_count"] == 3
    assert (tmp_path / "showcase" / "showcase.json").exists()
    assert (tmp_path / "showcase" / "showcase.md").exists()
