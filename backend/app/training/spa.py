"""SPA-style training data preparation.

This module does not train a policy model. It prepares deterministic
Stepwise Progress Attribution (SPA) style labels from existing LightClaw
trajectories so the exported data can be wired into a later PPO/GRPO setup.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

POSITIVE_STATUS = {"success"}
SAFE_STOP_REASONS = {"login_required", "captcha_blocked", "safe_stop", "task_completed"}


class SPAStepLabel(BaseModel):
    step_id: str
    trace_id: str
    action_type: str
    action_name: str | None = None
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    observation: Any = None
    status: str | None = None
    error_type: str | None = None
    stop_reason: str | None = None
    progress_score: float = Field(ge=0.0, le=1.0)
    action_validity: float = Field(ge=0.0, le=1.0)
    dense_reward: float
    reward_notes: list[str] = Field(default_factory=list)


class SPARolloutSample(BaseModel):
    task_id: str
    trace_id: str
    prompt: str
    source: str
    final_reward: float = Field(ge=0.0, le=1.0)
    total_dense_reward: float
    steps: list[SPAStepLabel]
    metadata: dict[str, Any] = Field(default_factory=dict)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            count += 1
    return count


def action_validity(action: dict[str, Any]) -> float:
    """Grounding/action-validity signal used by SPA-style dense reward."""
    status = action.get("status")
    stop_reason = action.get("stop_reason")
    if status in POSITIVE_STATUS:
        return 1.0
    if stop_reason in SAFE_STOP_REASONS:
        return 1.0
    if action.get("error_type"):
        return 0.0
    return 0.5


def estimate_final_reward(actions: list[dict[str, Any]], explicit_reward: float | None = None) -> float:
    """Estimate final outcome reward from a candidate trajectory.

    This is a deterministic proxy. Real SPA-RL would use environment outcomes
    or a learned progress estimator; we intentionally do neither here.
    """
    if explicit_reward is not None:
        return max(0.0, min(float(explicit_reward), 1.0))
    if not actions:
        return 0.0
    if any(action.get("stop_reason") in SAFE_STOP_REASONS for action in actions):
        return 1.0
    if actions[-1].get("status") == "success":
        return 1.0
    return 0.0


def redistribute_progress(actions: list[dict[str, Any]], final_reward: float) -> list[float]:
    """Redistribute final reward across valid/progressive steps.

    The scores sum to ``final_reward``. Valid terminal safety stops are counted
    as progress because the correct behavior is to stop instead of submitting,
    uploading, or bypassing login/CAPTCHA.
    """
    if not actions or final_reward <= 0:
        return [0.0 for _ in actions]

    weights: list[float] = []
    for action in actions:
        status = action.get("status")
        stop_reason = action.get("stop_reason")
        error_type = action.get("error_type")
        weight = 0.0
        if status == "success":
            weight = 1.0
        if stop_reason in SAFE_STOP_REASONS:
            weight = max(weight, 1.0)
        if error_type:
            weight = 0.0
        weights.append(weight)

    total = sum(weights)
    if total <= 0:
        # Some exported rejected candidates can still have a non-zero rule reward
        # from format validity or partial task signals. Keep the SPA cumulative
        # constraint intact while action_validity continues to mark them as bad.
        uniform = final_reward / len(actions)
        return [uniform for _ in actions]
    return [final_reward * weight / total for weight in weights]


def build_spa_rollout(
    *,
    task_id: str,
    prompt: str,
    actions: list[dict[str, Any]],
    source: str,
    explicit_reward: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> SPARolloutSample:
    final_reward = estimate_final_reward(actions, explicit_reward)
    progress_scores = redistribute_progress(actions, final_reward)
    steps: list[SPAStepLabel] = []
    trace_id = actions[0].get("trace_id", task_id) if actions else task_id
    for index, action in enumerate(actions):
        validity = action_validity(action)
        progress = progress_scores[index]
        dense_reward = progress + 0.1 * validity
        notes: list[str] = []
        if progress > 0:
            notes.append("progress_attributed")
        if validity == 1.0:
            notes.append("action_valid")
        if action.get("stop_reason") in SAFE_STOP_REASONS:
            notes.append("safe_stop_is_positive_behavior")
        if action.get("error_type"):
            notes.append("error_action_no_progress")
        steps.append(SPAStepLabel(
            step_id=str(action.get("step_id") or f"{trace_id}:{index + 1}"),
            trace_id=str(action.get("trace_id") or trace_id),
            action_type=str(action.get("action_type") or "tool_call"),
            action_name=action.get("action_name"),
            tool_name=action.get("tool_name"),
            arguments=action.get("arguments") or {},
            observation=action.get("observation"),
            status=action.get("status"),
            error_type=action.get("error_type"),
            stop_reason=action.get("stop_reason"),
            progress_score=progress,
            action_validity=validity,
            dense_reward=dense_reward,
            reward_notes=notes,
        ))

    return SPARolloutSample(
        task_id=task_id,
        trace_id=str(trace_id),
        prompt=prompt,
        source=source,
        final_reward=final_reward,
        total_dense_reward=sum(step.dense_reward for step in steps),
        steps=steps,
        metadata=metadata or {},
    )


def build_spa_rollouts_from_export(input_dir: Path) -> list[SPARolloutSample]:
    """Create SPA-style rollouts from exported SFT and GRPO files."""
    rollouts: list[SPARolloutSample] = []

    for row in read_jsonl(input_dir / "sft.jsonl"):
        messages = row.get("messages") or []
        if len(messages) < 2:
            continue
        try:
            actions = json.loads(messages[-1]["content"])
        except Exception:
            continue
        metadata = row.get("metadata", {})
        rollouts.append(build_spa_rollout(
            task_id=metadata.get("task_id", f"sft_{len(rollouts)}"),
            prompt=messages[1].get("content", ""),
            actions=actions,
            source=metadata.get("source", "sft_export"),
            metadata={
                "family": "sft",
                "sample_type": metadata.get("sample_type"),
                "safety_domain": metadata.get("safety_domain"),
                "stop_reason_distribution": metadata.get("stop_reason_distribution"),
            },
        ))

    for row in read_jsonl(input_dir / "grpo.jsonl"):
        prompt = row.get("prompt", "")
        task_id = row.get("metadata", {}).get("task_id", f"grpo_{len(rollouts)}")
        source = row.get("metadata", {}).get("source", "grpo_export")
        for index, candidate in enumerate(row.get("candidate_trajectories", []), start=1):
            rollouts.append(build_spa_rollout(
                task_id=f"{task_id}:candidate_{index}",
                prompt=prompt,
                actions=candidate.get("actions", []),
                source=source,
                explicit_reward=candidate.get("final_score"),
                metadata={
                    "family": "grpo",
                    "candidate_label": candidate.get("label"),
                    "original_task_id": task_id,
                },
            ))

    return rollouts


def build_spa_data_card(rollouts: list[SPARolloutSample]) -> dict[str, Any]:
    steps = [step for rollout in rollouts for step in rollout.steps]
    safe_stop_steps = [step for step in steps if step.stop_reason in SAFE_STOP_REASONS]
    error_steps = [step for step in steps if step.error_type]
    return {
        "export_time": datetime.now().isoformat(),
        "rollout_count": len(rollouts),
        "step_count": len(steps),
        "avg_steps_per_rollout": len(steps) / len(rollouts) if rollouts else 0.0,
        "avg_final_reward": sum(rollout.final_reward for rollout in rollouts) / len(rollouts) if rollouts else 0.0,
        "avg_dense_reward": sum(step.dense_reward for step in steps) / len(steps) if steps else 0.0,
        "avg_action_validity": sum(step.action_validity for step in steps) / len(steps) if steps else 0.0,
        "safe_stop_step_count": len(safe_stop_steps),
        "error_step_count": len(error_steps),
        "reward_design": "dense_reward = stepwise_progress + 0.1 * action_validity",
        "training_status": "data_preparation_only_no_model_training",
    }


def prepare_spa_training_data(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    rollouts = build_spa_rollouts_from_export(input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rollout_rows = [rollout.model_dump(mode="json") for rollout in rollouts]
    step_rows = [
        {
            "task_id": rollout.task_id,
            "prompt": rollout.prompt,
            "final_reward": rollout.final_reward,
            **step.model_dump(mode="json"),
        }
        for rollout in rollouts
        for step in rollout.steps
    ]
    ppo_rows = [
        {
            "prompt": rollout.prompt,
            "trajectory": [step.model_dump(mode="json") for step in rollout.steps],
            "dense_rewards": [step.dense_reward for step in rollout.steps],
            "final_reward": rollout.final_reward,
            "metadata": {
                "task_id": rollout.task_id,
                "trace_id": rollout.trace_id,
                "source": rollout.source,
                **rollout.metadata,
            },
        }
        for rollout in rollouts
    ]
    data_card = build_spa_data_card(rollouts)

    counts = {
        "spa_rollouts": write_jsonl(output_dir / "spa_rollouts.jsonl", rollout_rows),
        "progress_attribution": write_jsonl(output_dir / "progress_attribution.jsonl", step_rows),
        "ppo_ready": write_jsonl(output_dir / "ppo_ready.jsonl", ppo_rows),
    }
    data_card_path = output_dir / "spa_data_card.json"
    data_card_path.write_text(json.dumps(data_card, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "files": {
            "spa_rollouts": {"path": str(output_dir / "spa_rollouts.jsonl"), "count": counts["spa_rollouts"]},
            "progress_attribution": {"path": str(output_dir / "progress_attribution.jsonl"), "count": counts["progress_attribution"]},
            "ppo_ready": {"path": str(output_dir / "ppo_ready.jsonl"), "count": counts["ppo_ready"]},
            "spa_data_card": {"path": str(data_card_path), **data_card},
        },
    }
