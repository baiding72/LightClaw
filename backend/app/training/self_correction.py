"""Self-correction sample construction and metrics."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel

from app.eval.reward import RuleBasedVerifier


class SelfCorrectionSample(BaseModel):
    original_prompt: str
    attempt_action: dict[str, Any]
    observation: Any | None = None
    error: str | None = None
    verifier_feedback: str | None = None
    error_type: str | None = None
    revision_action: dict[str, Any] | None = None
    final_status: str
    recovery_success: bool
    over_correction: bool = False
    trace_id: str
    task_id: str
    reward_before: float = 0.0
    reward_after: float = 0.0


def _changed_action(attempt: dict[str, Any], revision: dict[str, Any]) -> bool:
    return (
        attempt.get("tool_name") != revision.get("tool_name")
        or attempt.get("action_name") != revision.get("action_name")
        or attempt.get("arguments") != revision.get("arguments")
        or attempt.get("action_type") != revision.get("action_type")
    )


def construct_self_correction_samples(
    trajectories: list[dict[str, Any]],
) -> list[SelfCorrectionSample]:
    """Build attempt-feedback-revision samples from action trajectories."""
    verifier = RuleBasedVerifier()
    samples: list[SelfCorrectionSample] = []
    for item in trajectories:
        actions = item.get("actions", [])
        for index, attempt in enumerate(actions[:-1]):
            revision = actions[index + 1]
            attempt_failed = attempt.get("status") == "failed" or bool(attempt.get("error_type"))
            attempt_correct = attempt.get("status") == "success" and not attempt.get("error_type")
            revision_success = revision.get("status") == "success"
            has_revision = revision.get("action_type") in {
                "self_correction",
                "tool_call",
                "ask_user",
                "final_answer",
                "gui_grounding",
                "gui_click",
            }
            is_marked_revision = revision.get("action_type") == "self_correction"
            is_over_correction = (
                attempt_correct
                and is_marked_revision
                and _changed_action(attempt, revision)
                and (
                    revision.get("error_type") == "over_correction"
                    or "过度修正" in str(revision.get("metadata", {}).get("feedback", ""))
                    or "错误修改" in str(revision.get("metadata", {}).get("feedback", ""))
                )
            )
            if not ((attempt_failed and has_revision) or is_over_correction):
                continue

            before = verifier.score([attempt], task_success=attempt_correct)
            after = verifier.score([attempt, revision], task_success=revision_success and not is_over_correction)
            samples.append(
                SelfCorrectionSample(
                    original_prompt=item.get("instruction", ""),
                    attempt_action=attempt,
                    observation=attempt.get("observation"),
                    error=attempt.get("error_message"),
                    verifier_feedback=(
                        attempt.get("metadata", {}).get("verifier_feedback")
                        or revision.get("metadata", {}).get("feedback")
                    ),
                    error_type=attempt.get("error_type") or ("over_correction" if is_over_correction else None),
                    revision_action=revision,
                    final_status=revision.get("status", "unknown"),
                    recovery_success=bool(attempt_failed and revision_success),
                    over_correction=is_over_correction,
                    trace_id=attempt.get("trace_id") or revision.get("trace_id") or item.get("task_id", ""),
                    task_id=item.get("task_id", ""),
                    reward_before=before.final_score,
                    reward_after=after.final_score,
                )
            )
    return samples


def calculate_self_correction_metrics(samples: list[SelfCorrectionSample], total_tasks: int) -> dict[str, Any]:
    total = len(samples)
    if total == 0:
        return {
            "correction_attempt_rate": 0.0,
            "recovery_success_rate": 0.0,
            "over_correction_rate": 0.0,
            "first_error_type_distribution": {},
            "revision_valid_rate": 0.0,
            "revision_improves_reward_rate": 0.0,
        }

    error_types = Counter(sample.error_type or "unknown" for sample in samples)
    valid_revisions = [
        sample for sample in samples
        if sample.revision_action is not None and sample.revision_action.get("status") == "success"
    ]
    improved = [sample for sample in samples if sample.reward_after > sample.reward_before]
    recoveries = [sample for sample in samples if sample.recovery_success]
    over_corrections = [sample for sample in samples if sample.over_correction]
    return {
        "correction_attempt_rate": total / max(total_tasks, 1),
        "recovery_success_rate": len(recoveries) / total,
        "over_correction_rate": len(over_corrections) / total,
        "first_error_type_distribution": dict(error_types),
        "revision_valid_rate": len(valid_revisions) / total,
        "revision_improves_reward_rate": len(improved) / total,
    }
