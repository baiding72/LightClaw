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
run_all_checks = run_all_checks_module.run_all_checks
dry_run = train_stub_module.dry_run


def test_run_all_checks_smoke_with_mocked_subprocess(monkeypatch, tmp_path) -> None:
    def fake_run(command, cwd, check, text, capture_output):  # noqa: ANN001
        del cwd, check, text, capture_output
        stdout = "# replay" if "replay_trace.py" in command else "{}"
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(run_all_checks_module, "DEFAULT_EXPORT_DIR", tmp_path / "exports")
    monkeypatch.setattr(run_all_checks_module, "DEFAULT_REPLAY_PATH", tmp_path / "replay.md")
    monkeypatch.setattr(subprocess, "run", fake_run)

    summary = run_all_checks()

    assert summary["passed"] is True
    assert Path(summary["replay_output_path"]).exists()
    assert len(summary["checks"]) == 3


def test_run_all_checks_reports_failure(monkeypatch, tmp_path) -> None:
    def fake_run(command, cwd, check, text, capture_output):  # noqa: ANN001
        del cwd, check, text, capture_output
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="boom")

    monkeypatch.setattr(run_all_checks_module, "DEFAULT_EXPORT_DIR", tmp_path / "exports")
    monkeypatch.setattr(run_all_checks_module, "DEFAULT_REPLAY_PATH", tmp_path / "replay.md")
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
