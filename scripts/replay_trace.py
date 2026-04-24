#!/usr/bin/env python3
"""Replay deterministic or recorded LightClaw traces in a human-readable form."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.eval.deterministic import get_fixture_case  # noqa: E402
from app.training.exporter import actions_from_events, load_trajectory_events  # noqa: E402
from app.training.replay import render_replay  # noqa: E402


def _load_trace(trace_id: str) -> dict | None:
    settings = get_settings()
    events = load_trajectory_events(Path(settings.trajectories_dir))
    actions = [action for action in actions_from_events(events) if action.get("trace_id") == trace_id]
    if not actions:
        return None
    return {
        "task_id": actions[0].get("trace_id", trace_id),
        "instruction": f"Replay recorded trace {trace_id}",
        "actions": actions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay LightClaw trace.")
    parser.add_argument("--trace-id", default=None)
    parser.add_argument("--fixture-case", default=None)
    args = parser.parse_args()

    if not args.trace_id and not args.fixture_case:
        raise SystemExit("Provide --trace-id or --fixture-case")

    case = get_fixture_case(args.fixture_case) if args.fixture_case else _load_trace(args.trace_id)
    if not case:
        raise SystemExit("Trace or fixture case not found.")
    print(render_replay(case))


if __name__ == "__main__":
    main()
