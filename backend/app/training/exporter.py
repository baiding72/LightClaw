"""SFT/DPO/GRPO-ready JSONL export helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Optional

from app.eval.deterministic import build_demo_action_trajectories
from app.eval.reward import RuleBasedVerifier

SYSTEM_PROMPT = (
    "你是一个集成在浏览器插件和本地工具运行时中的个人效率 Agent。"
    "你必须选择合法工具、填充完整参数，并根据 observation/error feedback 做自我修正。"
)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            count += 1
    return count


def load_trajectory_events(trajectory_dir: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not trajectory_dir.exists():
        return events
    for path in sorted(trajectory_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event["_source_file"] = str(path)
            events.append(event)
    return events


def actions_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for event in events:
        if event.get("event_type") != "step":
            continue
        if event.get("action"):
            actions.append(event["action"])
            continue
        chosen_tool = event.get("chosen_tool")
        if not chosen_tool and not event.get("gui_action_type"):
            continue
        status = "failed" if event.get("error_type") else "success"
        actions.append({
            "action_type": "gui_click" if event.get("gui_action_type") else "tool_call",
            "step_id": event.get("event_id") or f"{event.get('task_id')}:{event.get('step_index')}",
            "trace_id": event.get("trajectory_id") or f"traj_{event.get('task_id', 'unknown')}",
            "action_name": event.get("gui_action_type") or chosen_tool,
            "tool_name": chosen_tool,
            "arguments": event.get("tool_args") or {},
            "observation": event.get("observation") or event.get("tool_result"),
            "status": status,
            "error_type": event.get("error_type"),
            "error_message": event.get("error_message"),
            "timestamp": event.get("timestamp"),
            "latency_ms": event.get("latency_ms") or 0,
            "metadata": {"source_file": event.get("_source_file")},
        })
    return actions


def build_sft_rows(trajectories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in trajectories:
        successful = [a for a in item["actions"] if a.get("status") == "success"]
        if not successful:
            continue
        rows.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": item["instruction"]},
                {"role": "assistant", "content": json.dumps(successful, ensure_ascii=False)},
            ],
            "metadata": {
                "task_id": item["task_id"],
                "sample_type": "sft",
                "source": item.get("source", "trajectory"),
            },
        })
    return rows


def build_dpo_rows(trajectories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in trajectories:
        actions = item["actions"]
        for index, action in enumerate(actions[:-1]):
            next_action = actions[index + 1]
            is_failed = action.get("status") == "failed"
            is_repair = next_action.get("status") == "success" and next_action.get("action_type") in {
                "self_correction",
                "tool_call",
            }
            if is_failed and is_repair:
                rows.append({
                    "system": SYSTEM_PROMPT,
                    "prompt": item["instruction"],
                    "chosen": json.dumps(next_action, ensure_ascii=False),
                    "rejected": json.dumps(action, ensure_ascii=False),
                    "metadata": {
                        "task_id": item["task_id"],
                        "source": item.get("source", "trajectory"),
                        "failure_type": action.get("error_type"),
                    },
                })
    return rows


def build_grpo_rows(trajectories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    verifier = RuleBasedVerifier()
    rows: list[dict[str, Any]] = []
    for item in trajectories:
        reward = verifier.score(
            item["actions"],
            expected_actions=item.get("expected_actions", []),
            task_success=item.get("task_success"),
        )
        rows.append({
            "prompt": item["instruction"],
            "candidate_trajectories": [item["actions"]],
            "reward_breakdown": reward.model_dump(),
            "final_score": reward.final_score,
            "metadata": {
                "task_id": item["task_id"],
                "source": item.get("source", "trajectory"),
            },
        })
    return rows


def build_export_rows(
    *,
    trajectory_dir: Optional[Path] = None,
    include_fixtures: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    trajectories: list[dict[str, Any]] = []
    if trajectory_dir:
        events = load_trajectory_events(trajectory_dir)
        actions = actions_from_events(events)
        if actions:
            trajectories.append({
                "task_id": "real_trajectories",
                "instruction": "Exported from recorded LightClaw trajectories.",
                "actions": actions,
                "source": "trajectory",
            })
    if include_fixtures:
        for item in build_demo_action_trajectories():
            item = dict(item)
            item["source"] = "deterministic_fixture"
            trajectories.append(item)

    return {
        "sft": build_sft_rows(trajectories),
        "dpo": build_dpo_rows(trajectories),
        "grpo": build_grpo_rows(trajectories),
    }


def export_training_data(
    *,
    output_dir: Path,
    trajectory_dir: Optional[Path] = None,
    include_fixtures: bool = False,
) -> dict[str, Any]:
    rows = build_export_rows(
        trajectory_dir=trajectory_dir,
        include_fixtures=include_fixtures,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {"output_dir": str(output_dir), "files": {}}
    for name, records in rows.items():
        path = output_dir / f"{name}.jsonl"
        count = write_jsonl(path, records)
        result["files"][name] = {"path": str(path), "count": count}
    return result
