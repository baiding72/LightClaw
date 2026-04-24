#!/usr/bin/env python3
"""Dry-run training stub for exported LightClaw datasets.

This script does not train a model. It validates exported SFT/DPO/GRPO files
and prints small previews showing how the data can be wired into TRL,
LLaMA-Factory or verl.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_FILES = {
    "sft": "sft.jsonl",
    "dpo": "dpo.jsonl",
    "grpo": "grpo.jsonl",
    "self_correction": "self_correction.jsonl",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Required dataset file not found: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number} is not valid JSON: {exc}") from exc
    return rows


def validate_sft(rows: list[dict[str, Any]]) -> None:
    for index, row in enumerate(rows, start=1):
        messages = row.get("messages")
        if not isinstance(messages, list) or len(messages) < 2:
            raise ValueError(f"SFT row {index} must contain messages list.")


def validate_dpo(rows: list[dict[str, Any]]) -> None:
    for index, row in enumerate(rows, start=1):
        for key in ["system", "prompt", "chosen", "rejected"]:
            if key not in row:
                raise ValueError(f"DPO row {index} missing {key}.")
        json.loads(row["chosen"])
        json.loads(row["rejected"])


def validate_grpo(rows: list[dict[str, Any]]) -> None:
    for index, row in enumerate(rows, start=1):
        candidates = row.get("candidate_trajectories")
        if not isinstance(candidates, list) or len(candidates) < 2:
            raise ValueError(f"GRPO row {index} must contain at least 2 candidates.")
        for candidate in candidates:
            if "reward_breakdown" not in candidate:
                raise ValueError(f"GRPO row {index} candidate missing reward_breakdown.")


def validate_self_correction(rows: list[dict[str, Any]]) -> None:
    required = {"original_prompt", "attempt_action", "error_type", "final_status", "trace_id", "task_id"}
    for index, row in enumerate(rows, start=1):
        missing = required - set(row)
        if missing:
            raise ValueError(f"Self-correction row {index} missing {sorted(missing)}.")


def preview_row(row: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(row, ensure_ascii=False)
    return {"preview": text[:500] + ("..." if len(text) > 500 else "")}


def dry_run(input_dir: Path) -> dict[str, Any]:
    datasets = {
        name: read_jsonl(input_dir / filename)
        for name, filename in REQUIRED_FILES.items()
    }
    validate_sft(datasets["sft"])
    validate_dpo(datasets["dpo"])
    validate_grpo(datasets["grpo"])
    validate_self_correction(datasets["self_correction"])

    data_card_path = input_dir / "data_card.json"
    data_card = json.loads(data_card_path.read_text(encoding="utf-8")) if data_card_path.exists() else None
    return {
        "input_dir": str(input_dir),
        "ready": True,
        "message": "ready for SFT/DPO/GRPO training",
        "counts": {name: len(rows) for name, rows in datasets.items()},
        "previews": {
            name: preview_row(rows[0]) if rows else {"preview": "<empty>"}
            for name, rows in datasets.items()
        },
        "data_card": data_card,
        "next_steps": [
            "SFT: map sft.jsonl messages into a supervised fine-tuning trainer.",
            "DPO: feed dpo.jsonl system/prompt/chosen/rejected into a preference trainer.",
            "GRPO/verl: use grpo.jsonl candidate_trajectories and reward_breakdown as rollout fixtures.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate exported datasets without training.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--dry-run", action="store_true", help="Validate and preview only. No training is launched.")
    args = parser.parse_args()
    if not args.dry_run:
        raise SystemExit("This repository only supports --dry-run. Real training is intentionally not launched.")
    result = dry_run(Path(args.input_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
