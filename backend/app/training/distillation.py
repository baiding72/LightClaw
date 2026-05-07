"""Trajectory distillation for training data preparation."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app.training.exporter import (
    actions_from_events,
    classify_trajectory,
    load_trajectory_events,
    write_jsonl,
)


def _compact_action(action: dict[str, Any], *, dom_limit: int = 800) -> dict[str, Any]:
    compact = {
        "step_id": action.get("step_id"),
        "trace_id": action.get("trace_id"),
        "action_type": action.get("action_type"),
        "tool_name": action.get("tool_name"),
        "action_name": action.get("action_name"),
        "arguments": action.get("arguments") or {},
        "status": action.get("status"),
        "error_type": action.get("error_type"),
        "error_message": action.get("error_message"),
        "stop_reason": action.get("stop_reason"),
        "page_url": action.get("page_url"),
        "page_title": action.get("page_title"),
        "extraction_result": action.get("extraction_result"),
        "metadata": action.get("metadata") or {},
    }
    dom_snapshot = action.get("dom_snapshot")
    if dom_snapshot:
        compact["dom_snapshot"] = str(dom_snapshot)[:dom_limit]
        compact["dom_truncated"] = len(str(dom_snapshot)) > dom_limit
    return compact


def _quality_score(actions: list[dict[str, Any]]) -> float:
    if not actions:
        return 0.0
    positives = 0
    for action in actions:
        if action.get("status") == "success":
            positives += 1
        if action.get("stop_reason") in {"login_required", "captcha_blocked", "safe_stop", "task_completed"}:
            positives += 1
    errors = sum(1 for action in actions if action.get("error_type"))
    return max(0.0, min((positives - errors) / len(actions), 1.0))


def distill_trajectories(
    *,
    trajectory_dir: Path,
    output_dir: Path,
    include_failed: bool = True,
) -> dict[str, Any]:
    """Create compact, training-oriented trajectories from raw logged events."""
    events = load_trajectory_events(trajectory_dir)
    actions = actions_from_events(events)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for action in actions:
        trace_id = action.get("trace_id") or "unknown_trace"
        grouped.setdefault(trace_id, []).append(action)

    rows: list[dict[str, Any]] = []
    for trace_id, trace_actions in grouped.items():
        has_failure = any(action.get("status") == "failed" or action.get("error_type") for action in trace_actions)
        if has_failure and not include_failed:
            continue
        tags = classify_trajectory(trace_actions)
        compact_actions = [_compact_action(action) for action in trace_actions]
        stop_reasons = Counter(action.get("stop_reason") for action in trace_actions if action.get("stop_reason"))
        error_types = Counter(action.get("error_type") for action in trace_actions if action.get("error_type"))
        rows.append({
            "trace_id": trace_id,
            "task_id": trace_id,
            "source": "recorded_trajectory",
            "distilled_at": datetime.now().isoformat(),
            "sample_type": tags.get("sample_type", "trajectory_distilled"),
            "safety_domain": tags.get("safety_domain"),
            "quality_score": _quality_score(trace_actions),
            "step_count": len(compact_actions),
            "stop_reason_distribution": dict(stop_reasons),
            "error_type_distribution": dict(error_types),
            "actions": compact_actions,
            "distillation_notes": [
                "raw DOM snapshots truncated",
                "actions normalized to AgentAction-compatible fields",
                "safe-stop stop_reason preserved as positive behavior",
            ],
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    distilled_path = output_dir / "distilled_trajectories.jsonl"
    count = write_jsonl(distilled_path, rows)
    card = {
        "export_time": datetime.now().isoformat(),
        "source_trajectory_dir": str(trajectory_dir),
        "distilled_count": count,
        "avg_steps": sum(row["step_count"] for row in rows) / len(rows) if rows else 0.0,
        "avg_quality_score": sum(row["quality_score"] for row in rows) / len(rows) if rows else 0.0,
        "sample_type_distribution": dict(Counter(row["sample_type"] for row in rows)),
        "safe_stop_count": sum(1 for row in rows if row.get("sample_type") == "recruiting_safe_stop"),
        "include_failed": include_failed,
    }
    card_path = output_dir / "distillation_card.json"
    card_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "output_dir": str(output_dir),
        "files": {
            "distilled_trajectories": {"path": str(distilled_path), "count": count},
            "distillation_card": {"path": str(card_path), **card},
        },
    }
