"""SFT/DPO/GRPO-ready JSONL export helpers."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from app.eval.deterministic import build_demo_action_trajectories
from app.eval.reward import RuleBasedVerifier
from app.training.self_correction import construct_self_correction_samples

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
    verifier = RuleBasedVerifier()
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
                rejected_reward = verifier.score([action], task_success=False).final_score
                chosen_reward = verifier.score([action, next_action], task_success=True).final_score
                suspicious_pair = action == next_action or chosen_reward <= rejected_reward
                rows.append({
                    "system": SYSTEM_PROMPT,
                    "prompt": item["instruction"],
                    "chosen": json.dumps(next_action, ensure_ascii=False),
                    "rejected": json.dumps(action, ensure_ascii=False),
                    "metadata": {
                        "task_id": item["task_id"],
                        "source": item.get("source", "trajectory"),
                        "failure_type": action.get("error_type"),
                        "pair_reason": action.get("error_type") or "recovery_success",
                        "chosen_reward": chosen_reward,
                        "rejected_reward": rejected_reward,
                        "suspicious_pair": suspicious_pair,
                    },
                })
    return rows


def build_grpo_rows(trajectories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    verifier = RuleBasedVerifier()
    rows: list[dict[str, Any]] = []
    for item in trajectories:
        samples = construct_self_correction_samples([item])
        if not samples:
            continue
        candidates: list[dict[str, Any]] = []
        for sample in samples:
            rejected_actions = [sample.attempt_action]
            chosen_actions = [sample.attempt_action]
            if sample.revision_action:
                chosen_actions.append(sample.revision_action)
            for label, candidate_actions, task_success in [
                ("rejected", rejected_actions, False),
                ("chosen", chosen_actions, sample.recovery_success and not sample.over_correction),
            ]:
                reward = verifier.score(
                    candidate_actions,
                    expected_actions=item.get("expected_actions", []),
                    task_success=task_success,
                )
                candidates.append({
                    "label": label,
                    "actions": candidate_actions,
                    "reward_breakdown": reward.model_dump(),
                    "final_score": reward.final_score,
                })
        if not candidates:
            continue
        scores = [candidate["final_score"] for candidate in candidates]
        rows.append({
            "prompt": item["instruction"],
            "candidate_trajectories": candidates,
            "reward_breakdown": candidates[-1]["reward_breakdown"],
            "final_score": max(scores),
            "metadata": {
                "task_id": item["task_id"],
                "source": item.get("source", "trajectory"),
                "low_signal_group": len(candidates) < 2 or len(set(scores)) <= 1,
            },
        })
    return rows


def build_self_correction_rows(trajectories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        sample.model_dump(mode="json")
        for sample in construct_self_correction_samples(trajectories)
    ]


def build_export_rows(
    *,
    trajectory_dir: Path | None = None,
    include_fixtures: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    trajectories: list[dict[str, Any]] = []
    if trajectory_dir:
        events = load_trajectory_events(trajectory_dir)
        actions = actions_from_events(events)
        grouped_actions: dict[str, list[dict[str, Any]]] = {}
        for action in actions:
            trace_id = action.get("trace_id") or "unknown_trace"
            grouped_actions.setdefault(trace_id, []).append(action)
        for trace_id, trace_actions in grouped_actions.items():
            trajectories.append({
                "task_id": trace_id,
                "instruction": f"Exported from recorded LightClaw trajectory {trace_id}.",
                "actions": trace_actions,
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
        "self_correction": build_self_correction_rows(trajectories),
    }


def _distribution(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for row in rows:
        value = row.get(key)
        if not value:
            continue
        distribution[str(value)] = distribution.get(str(value), 0) + 1
    return distribution


def build_data_card(
    rows: dict[str, list[dict[str, Any]]],
    *,
    source: str,
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    for sft in rows.get("sft", []):
        try:
            actions.extend(json.loads(sft["messages"][-1]["content"]))
        except Exception:
            pass
    for sample in rows.get("self_correction", []):
        actions.append(sample.get("attempt_action", {}))
        if sample.get("revision_action"):
            actions.append(sample["revision_action"])

    dpo_rows = rows.get("dpo", [])
    grpo_rows = rows.get("grpo", [])
    suspicious = [row for row in dpo_rows if row.get("metadata", {}).get("suspicious_pair")]
    low_signal = [row for row in grpo_rows if row.get("metadata", {}).get("low_signal_group")]
    invalid_samples = len(suspicious) + len(low_signal)
    chosen_rewards = [
        row.get("metadata", {}).get("chosen_reward", 0.0)
        for row in dpo_rows
    ]
    rejected_rewards = [
        row.get("metadata", {}).get("rejected_reward", 0.0)
        for row in dpo_rows
    ]
    error_distribution = _distribution(
        [sample for sample in rows.get("self_correction", []) if sample.get("error_type")],
        "error_type",
    )
    action_distribution = _distribution(actions, "action_type")
    total_samples = sum(len(value) for value in rows.values())
    valid_samples = max(total_samples - invalid_samples, 0)
    step_counts = [
        len(candidate.get("actions", []))
        for row in grpo_rows
        for candidate in row.get("candidate_trajectories", [])
    ]
    return {
        "export_time": datetime.now().isoformat(),
        "source": source,
        "sft_count": len(rows.get("sft", [])),
        "dpo_pair_count": len(dpo_rows),
        "grpo_group_count": len(grpo_rows),
        "self_correction_count": len(rows.get("self_correction", [])),
        "error_type_distribution": error_distribution,
        "action_type_distribution": action_distribution,
        "avg_steps": sum(step_counts) / len(step_counts) if step_counts else 0.0,
        "chosen_reward_avg": sum(chosen_rewards) / len(chosen_rewards) if chosen_rewards else 0.0,
        "rejected_reward_avg": sum(rejected_rewards) / len(rejected_rewards) if rejected_rewards else 0.0,
        "invalid_sample_count": invalid_samples,
        "schema_validation_pass_rate": valid_samples / total_samples if total_samples else 1.0,
        "suspicious_pair_count": len(suspicious),
        "low_signal_group_count": len(low_signal),
    }


def export_training_data(
    *,
    output_dir: Path,
    trajectory_dir: Path | None = None,
    include_fixtures: bool = False,
    with_data_card: bool = False,
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
    if with_data_card:
        source = "trajectory+deterministic_fixture" if include_fixtures and trajectory_dir else (
            "deterministic_fixture" if include_fixtures else "trajectory"
        )
        data_card = build_data_card(rows, source=source)
        data_card_path = output_dir / "data_card.json"
        data_card_path.write_text(json.dumps(data_card, ensure_ascii=False, indent=2), encoding="utf-8")
        result["data_card"] = {"path": str(data_card_path), **data_card}
    return result
