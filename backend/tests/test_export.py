import json

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
