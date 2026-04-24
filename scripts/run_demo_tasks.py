#!/usr/bin/env python3
"""Run deterministic LightClaw demo trajectories without an LLM API key."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.eval.deterministic import build_demo_action_trajectories


def write_fixture_trajectories(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for item in build_demo_action_trajectories():
        path = output_dir / f"trajectory_{item['task_id']}_{timestamp}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "event_type": "task",
                "task_id": item["task_id"],
                "user_instruction": item["instruction"],
                "source": "deterministic_fixture",
                "timestamp": datetime.now().isoformat(),
            }, ensure_ascii=False) + "\n")
            for index, action in enumerate(item["actions"], start=1):
                handle.write(json.dumps({
                    "event_type": "step",
                    "event_id": action["step_id"],
                    "task_id": item["task_id"],
                    "trajectory_id": action["trace_id"],
                    "step_index": index,
                    "chosen_tool": action.get("tool_name"),
                    "tool_args": action.get("arguments"),
                    "error_type": action.get("error_type"),
                    "error_message": action.get("error_message"),
                    "latency_ms": action.get("latency_ms"),
                    "observation": action.get("observation"),
                    "action": action,
                    "timestamp": datetime.now().isoformat(),
                }, ensure_ascii=False) + "\n")
        written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic LightClaw demo tasks.")
    parser.add_argument("--mock", action="store_true", help="Use deterministic fixtures. This is the default.")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    settings = get_settings()
    output_dir = Path(args.output_dir or settings.trajectories_dir)
    written = write_fixture_trajectories(output_dir)

    print("LightClaw deterministic demo completed.")
    print(f"Trajectories written: {len(written)}")
    for path in written:
        print(f"- {path}")


if __name__ == "__main__":
    main()
