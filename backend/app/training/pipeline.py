"""End-to-end deterministic training pipeline orchestration."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.eval.deterministic import build_deterministic_evaluation
from app.eval.reports import ReportGenerator
from app.recruiting.collector import collect_fixture_trajectories
from app.training.distillation import distill_trajectories
from app.training.exporter import export_training_data
from app.training.spa import prepare_spa_training_data


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "recruiting"


def _write_eval_report(output_dir: Path) -> dict[str, Any]:
    result = build_deterministic_evaluation("training_pipeline_eval")
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = result.model_dump(mode="json")
    payload["mode"] = "deterministic"
    payload["source"] = "deterministic_fixture"
    (output_dir / "latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = ReportGenerator(output_dir=str(output_dir)).generate_markdown_report(result)
    (output_dir / "latest.md").write_text(report, encoding="utf-8")
    return {
        "report_path": str(output_dir / "latest.json"),
        "task_success_rate": result.metrics.task_success_rate,
        "recovery_rate": result.metrics.recovery_rate,
        "gui_grounding_accuracy": result.metrics.gui_action_accuracy,
    }


def _build_stage(
    *,
    name: str,
    status: str,
    output: dict[str, Any],
    purpose: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "purpose": purpose,
        "output": output,
    }


def run_training_pipeline(
    *,
    output_root: Path | None = None,
    include_fixtures: bool = True,
) -> dict[str, Any]:
    """Run the local training-preparation pipeline.

    This pipeline performs data preparation only. It does not launch SFT,
    DPO, PPO, GRPO, or any GPU training job.
    """
    settings = get_settings()
    data_dir = Path(settings.data_dir)
    output_root = output_root or data_dir / "training_pipeline" / "latest"
    output_root.mkdir(parents=True, exist_ok=True)

    trajectories_dir = data_dir / "trajectories"
    recruiting_output = trajectories_dir / "recruiting" / "latest"
    distilled_dir = output_root / "distilled"
    export_dir = output_root / "exports"
    spa_dir = output_root / "spa"
    eval_dir = output_root / "eval"

    stages: list[dict[str, Any]] = []

    collect_result = collect_fixture_trajectories(_fixture_dir(), recruiting_output)
    stages.append(_build_stage(
        name="trajectory_collection",
        status="passed",
        purpose="Collect safe dry-run recruiting traces without login/upload/submit.",
        output=collect_result,
    ))

    distill_result = distill_trajectories(
        trajectory_dir=trajectories_dir,
        output_dir=distilled_dir,
        include_failed=True,
    )
    stages.append(_build_stage(
        name="trajectory_distillation",
        status="passed",
        purpose="Compact raw traces into training-oriented trajectory records.",
        output=distill_result,
    ))

    export_result = export_training_data(
        output_dir=export_dir,
        trajectory_dir=trajectories_dir,
        include_fixtures=include_fixtures,
        with_data_card=True,
    )
    stages.append(_build_stage(
        name="sft_dpo_grpo_export",
        status="passed",
        purpose="Export SFT/DPO/GRPO/self-correction JSONL with data card.",
        output=export_result,
    ))

    spa_result = prepare_spa_training_data(export_dir, spa_dir)
    stages.append(_build_stage(
        name="spa_rl_preparation",
        status="passed",
        purpose="Prepare SPA-style progress attribution and PPO-ready dense reward rollouts.",
        output=spa_result,
    ))

    eval_result = _write_eval_report(eval_dir)
    stages.append(_build_stage(
        name="evaluation",
        status="passed",
        purpose="Run deterministic eval over tool-use, self-correction and GUI grounding fixtures.",
        output=eval_result,
    ))

    report = {
        "generated_at": datetime.now().isoformat(),
        "status": "passed",
        "training_status": "data_preparation_only_no_model_training",
        "output_root": str(output_root),
        "stages": stages,
        "recommended_real_training_order": [
            "SFT on successful distilled trajectories and tool-use messages",
            "DPO on chosen/rejected correction pairs",
            "SPA-style RL using ppo_ready.jsonl dense_rewards in PPO/GRPO trainer",
            "Evaluate on deterministic fixtures first, then separately on live/browser tasks",
        ],
        "explicit_non_claims": [
            "No model weights are trained by this pipeline.",
            "No real online success-rate improvement is claimed.",
            "No GPU or external LLM API key is required.",
        ],
    }
    report_path = output_root / "training_pipeline_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path = output_root / "training_pipeline_report.md"
    markdown_path.write_text(render_training_pipeline_markdown(report), encoding="utf-8")
    return {
        **report,
        "report_path": str(report_path),
        "markdown_path": str(markdown_path),
    }


def render_training_pipeline_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# LightClaw Training Pipeline",
        "",
        f"Generated at: `{report['generated_at']}`",
        f"Status: `{report['status']}`",
        f"Training status: `{report['training_status']}`",
        "",
        "## Stages",
        "",
    ]
    for stage in report["stages"]:
        lines.extend([
            f"### {stage['name']}",
            "",
            f"- Status: `{stage['status']}`",
            f"- Purpose: {stage['purpose']}",
            "",
        ])
    lines.extend([
        "## Real Training Order",
        "",
        *[f"- {item}" for item in report["recommended_real_training_order"]],
        "",
        "## Non-claims",
        "",
        *[f"- {item}" for item in report["explicit_non_claims"]],
        "",
    ])
    return "\n".join(lines)
