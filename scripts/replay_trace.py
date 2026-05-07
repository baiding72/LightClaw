#!/usr/bin/env python3
"""Replay deterministic or recorded LightClaw traces in a human-readable form."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402


def _load_trace(trace_id: str) -> dict | None:
    from app.training.exporter import actions_from_events, load_trajectory_events

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


def _load_recruiting_trace() -> dict | None:
    settings = get_settings()
    paths = [
        ROOT / "backend" / "data" / "trajectories" / "recruiting" / "latest" / "traces.jsonl",
        Path(settings.trajectories_dir) / "recruiting" / "latest" / "traces.jsonl",
    ]
    path = next((candidate for candidate in paths if candidate.exists()), paths[0])
    if not path.exists():
        return None
    actions = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not actions:
        return None
    return {
        "task_id": actions[0].get("trace_id", "recruiting_latest"),
        "instruction": "Safe dry-run recruiting trajectory collection.",
        "actions": actions,
    }


def _render_recruiting_replay(case: dict) -> str:
    lines = [
        f"# Recruiting Replay: {case.get('task_id')}",
        "",
    ]
    for index, action in enumerate(case.get("actions", []), start=1):
        action_name = action.get("action_name") or action.get("tool_name")
        if action_name == "open_url":
            label = f"open url `{action.get('page_url')}`"
        elif action_name == "extract_jobs":
            jobs = action.get("extraction_result", {}).get("jobs", [])
            label = f"extract jobs ({len(jobs)})"
        elif action_name == "click_job":
            label = f"click job `{action.get('page_title')}`"
        elif action.get("stop_reason"):
            label = f"detect {action.get('stop_reason')}"
        else:
            label = action_name or "action"
        lines.append(f"Step {index}: {label}")
    stop_reason = next(
        (action.get("stop_reason") for action in reversed(case.get("actions", [])) if action.get("stop_reason")),
        "unknown",
    )
    lines.extend(["", f"STOP: {stop_reason}"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay LightClaw trace.")
    parser.add_argument("--trace-id", default=None)
    parser.add_argument("--fixture-case", default=None)
    parser.add_argument("--trace-domain", choices=["recruiting"], default=None)
    args = parser.parse_args()

    if args.trace_domain == "recruiting":
        case = _load_recruiting_trace()
        if not case:
            raise SystemExit("Recruiting trace not found. Run collect_recruiting_trajectories.py --mode fixture first.")
        print(_render_recruiting_replay(case))
        return

    if not args.trace_id and not args.fixture_case:
        raise SystemExit("Provide --trace-id or --fixture-case")

    if args.fixture_case:
        from app.eval.deterministic import get_fixture_case

        case = get_fixture_case(args.fixture_case)
    else:
        case = _load_trace(args.trace_id)
    if not case:
        raise SystemExit("Trace or fixture case not found.")
    from app.training.replay import render_replay

    print(render_replay(case))


if __name__ == "__main__":
    main()
