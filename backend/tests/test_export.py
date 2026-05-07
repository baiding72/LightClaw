import json
from pathlib import Path

from app.training.exporter import export_training_data


def test_training_export_writes_sft_dpo_grpo_jsonl(tmp_path) -> None:
    result = export_training_data(output_dir=tmp_path, include_fixtures=True)

    assert result["files"]["sft"]["count"] >= 1
    assert result["files"]["dpo"]["count"] >= 1
    assert result["files"]["grpo"]["count"] >= 1

    dpo_line = (tmp_path / "dpo.jsonl").read_text(encoding="utf-8").splitlines()[0]
    dpo = json.loads(dpo_line)
    assert {"system", "prompt", "chosen", "rejected"}.issubset(dpo)
    assert json.loads(dpo["chosen"])["status"] == "success"
    assert json.loads(dpo["rejected"])["status"] == "failed"


def test_export_marks_fixture_source(tmp_path) -> None:
    export_training_data(output_dir=tmp_path, include_fixtures=True)
    grpo = json.loads((tmp_path / "grpo.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert grpo["metadata"]["source"] == "deterministic_fixture"


def test_export_reads_recruiting_normalized_actions_recursively(tmp_path) -> None:
    trajectory_dir = tmp_path / "trajectories"
    recruiting_dir = trajectory_dir / "recruiting" / "latest"
    recruiting_dir.mkdir(parents=True)
    (recruiting_dir / "traces.jsonl").write_text(
        json.dumps({
            "action_type": "tool_call",
            "step_id": "recruiting:1",
            "trace_id": "recruiting_trace",
            "tool_name": "recruiting_browser",
            "action_name": "extract_jobs",
            "arguments": {"action": "extract_jobs"},
            "status": "success",
            "page_url": "https://fixture.local/careers",
            "extraction_result": {"jobs": [{"title": "大语言模型算法实习生"}]},
            "stop_reason": "login_required",
        }) + "\n",
        encoding="utf-8",
    )

    result = export_training_data(output_dir=tmp_path / "exports", trajectory_dir=trajectory_dir)

    assert result["files"]["sft"]["count"] == 1
    sft = json.loads((tmp_path / "exports" / "sft.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert sft["metadata"]["source"] == "trajectory"
    assert sft["metadata"]["sample_type"] == "recruiting_safe_stop"
    assert sft["metadata"]["safety_domain"] == "recruiting"
    assert sft["metadata"]["stop_reason_distribution"] == {"login_required": 1}
    assert "login_required" in sft["messages"][-1]["content"]
    assert "recruiting_browser" in sft["messages"][-1]["content"]


def test_export_data_card_counts_recruiting_sample_type(tmp_path: Path) -> None:
    trajectory_dir = tmp_path / "trajectories"
    recruiting_dir = trajectory_dir / "recruiting" / "latest"
    recruiting_dir.mkdir(parents=True)
    (recruiting_dir / "traces.jsonl").write_text(
        "\n".join([
            json.dumps({
                "action_type": "tool_call",
                "step_id": "recruiting:1",
                "trace_id": "recruiting_trace",
                "tool_name": "recruiting_browser",
                "action_name": "extract_apply_flow",
                "arguments": {"action": "extract_apply_flow"},
                "status": "blocked",
                "stop_reason": "login_required",
            }),
            json.dumps({
                "action_type": "tool_call",
                "step_id": "recruiting:2",
                "trace_id": "recruiting_trace",
                "tool_name": "recruiting_browser",
                "action_name": "submit_application",
                "arguments": {"action": "submit_application"},
                "status": "blocked",
                "stop_reason": "safe_stop",
            }),
        ]) + "\n",
        encoding="utf-8",
    )

    result = export_training_data(
        output_dir=tmp_path / "exports",
        trajectory_dir=trajectory_dir,
        with_data_card=True,
    )

    assert result["data_card"]["sample_type_distribution"]["recruiting_safe_stop"] == 1
