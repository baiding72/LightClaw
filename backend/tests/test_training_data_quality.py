import json

from app.training.exporter import build_data_card, build_export_rows, export_training_data


def test_data_card_generation(tmp_path) -> None:
    result = export_training_data(output_dir=tmp_path, include_fixtures=True, with_data_card=True)

    card_path = tmp_path / "data_card.json"
    assert card_path.exists()
    card = json.loads(card_path.read_text(encoding="utf-8"))
    assert result["data_card"]["self_correction_count"] == card["self_correction_count"]
    assert card["dpo_pair_count"] > 0
    assert card["schema_validation_pass_rate"] >= 0


def test_dpo_suspicious_pair_detection() -> None:
    rows = {
        "sft": [],
        "dpo": [
            {
                "metadata": {
                    "chosen_reward": 0.1,
                    "rejected_reward": 0.9,
                    "suspicious_pair": True,
                }
            }
        ],
        "grpo": [],
        "self_correction": [],
    }
    card = build_data_card(rows, source="unit_test")

    assert card["suspicious_pair_count"] == 1
    assert card["invalid_sample_count"] == 1


def test_grpo_low_signal_group_detection() -> None:
    rows = {
        "sft": [],
        "dpo": [],
        "grpo": [
            {
                "candidate_trajectories": [
                    {"actions": [{"action_type": "tool_call"}], "reward_breakdown": {}, "final_score": 0.5},
                    {"actions": [{"action_type": "tool_call"}], "reward_breakdown": {}, "final_score": 0.5},
                ],
                "metadata": {"low_signal_group": True},
            }
        ],
        "self_correction": [],
    }
    card = build_data_card(rows, source="unit_test")

    assert card["low_signal_group_count"] == 1
    assert card["invalid_sample_count"] == 1


def test_export_rows_include_self_correction_and_grpo_candidates() -> None:
    rows = build_export_rows(include_fixtures=True)

    assert rows["self_correction"]
    assert rows["grpo"]
    assert len(rows["grpo"][0]["candidate_trajectories"]) >= 2
    assert "reward_breakdown" in rows["grpo"][0]["candidate_trajectories"][0]
