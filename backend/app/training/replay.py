"""Human-readable replay rendering for LightClaw traces."""

from __future__ import annotations

import json
from typing import Any

from app.eval.reward import RuleBasedVerifier
from app.training.self_correction import construct_self_correction_samples


def render_replay(case: dict[str, Any]) -> str:
    verifier = RuleBasedVerifier()
    samples = construct_self_correction_samples([case])
    lines = [
        f"# Replay: {case.get('task_id')}",
        "",
        f"Prompt: {case.get('instruction', '')}",
        "",
    ]
    for index, action in enumerate(case.get("actions", []), start=1):
        reward = verifier.score([action], task_success=action.get("status") == "success")
        lines.extend([
            f"## Step {index}",
            f"- Action: `{action.get('action_type')}` / `{action.get('tool_name') or action.get('action_name')}`",
            f"- Arguments: `{json.dumps(action.get('arguments', {}), ensure_ascii=False)}`",
            f"- Status: `{action.get('status')}`",
            f"- Observation: `{json.dumps(action.get('observation'), ensure_ascii=False)}`",
            f"- Error: `{action.get('error_type') or ''}` {action.get('error_message') or ''}",
            f"- Verifier feedback: {action.get('metadata', {}).get('verifier_feedback') or action.get('metadata', {}).get('feedback') or ''}",
            f"- Reward: {reward.final_score:.3f}",
            "",
        ])
    if samples:
        lines.append("## Revisions")
        for sample in samples:
            lines.extend([
                f"- Error type: `{sample.error_type}`",
                f"- Recovery success: `{sample.recovery_success}`",
                f"- Over correction: `{sample.over_correction}`",
                f"- Reward change: `{sample.reward_before:.3f} -> {sample.reward_after:.3f}`",
                "",
            ])
    return "\n".join(lines)
