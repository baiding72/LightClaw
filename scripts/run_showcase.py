#!/usr/bin/env python3
"""Build a one-file showcase report for the P0/P1/P2 demo chain."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from run_all_checks import BACKEND, run_all_checks  # noqa: E402

DEFAULT_SHOWCASE_DIR = BACKEND / "data" / "showcase" / "latest"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path, *, max_chars: int = 4000) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")[:max_chars]


def build_showcase(*, output_dir: Path = DEFAULT_SHOWCASE_DIR, with_pytest: bool = False) -> dict[str, Any]:
    """Run reproducibility checks and assemble a compact interview/demo report."""
    checks = run_all_checks(with_pytest=with_pytest)
    eval_report = _read_json(Path(checks["eval_report_path"]))
    data_card = _read_json(Path(checks["data_card_path"]))
    spa_data_card = _read_json(Path(checks.get("spa_data_card_path", "")))
    recruiting_replay = _read_text(Path(checks["recruiting_replay_output_path"]))
    correction_replay = _read_text(Path(checks["replay_output_path"]))

    showcase = {
        "generated_at": datetime.now().isoformat(),
        "passed": checks["passed"],
        "summary": {
            "p0_recruiting_safe_dry_run": {
                "status": "passed" if checks["passed"] else "failed",
                "metrics": eval_report.get("recruiting_metrics", {}),
                "trace_path": checks.get("recruiting_trace_path"),
                "replay_path": checks.get("recruiting_replay_output_path"),
            },
            "p1_skill_progressive_loading": {
                "status": "passed" if eval_report.get("skill_metrics") else "missing",
                "metrics": eval_report.get("skill_metrics", {}),
            },
            "p2_training_export_quality": {
                "status": "passed" if data_card else "missing",
                "data_card": {
                    "source": data_card.get("source"),
                    "sft_count": data_card.get("sft_count"),
                    "dpo_pair_count": data_card.get("dpo_pair_count"),
                    "grpo_group_count": data_card.get("grpo_group_count"),
                    "self_correction_count": data_card.get("self_correction_count"),
                    "schema_validation_pass_rate": data_card.get("schema_validation_pass_rate"),
                    "invalid_sample_count": data_card.get("invalid_sample_count"),
                    "sample_type_distribution": data_card.get("sample_type_distribution", {}),
                },
            },
            "p3_spa_training_preparation": {
                "status": "passed" if spa_data_card else "missing",
                "spa_data_card": spa_data_card,
            },
        },
        "paths": {
            "eval_report": checks.get("eval_report_path"),
            "training_export": checks.get("training_export_path"),
            "spa_training_export": checks.get("spa_training_export_path"),
            "data_card": checks.get("data_card_path"),
            "spa_data_card": checks.get("spa_data_card_path"),
            "recruiting_replay": checks.get("recruiting_replay_output_path"),
            "self_correction_replay": checks.get("replay_output_path"),
        },
        "replays": {
            "recruiting": recruiting_replay,
            "self_correction_wrong_args": correction_replay,
        },
        "checks": checks["checks"],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "showcase.json").write_text(
        json.dumps(showcase, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "showcase.md").write_text(render_showcase_markdown(showcase), encoding="utf-8")
    return showcase


def render_showcase_markdown(showcase: dict[str, Any]) -> str:
    summary = showcase["summary"]
    recruiting = summary["p0_recruiting_safe_dry_run"]["metrics"]
    skill = summary["p1_skill_progressive_loading"]["metrics"]
    export = summary["p2_training_export_quality"]["data_card"]
    spa = summary.get("p3_spa_training_preparation", {}).get("spa_data_card", {})
    return "\n".join([
        "# LightClaw Showcase",
        "",
        f"Generated at: `{showcase['generated_at']}`",
        f"Overall status: `{'passed' if showcase['passed'] else 'failed'}`",
        "",
        "## P0 Recruiting Safe Dry-run",
        "",
        f"- Jobs extracted: `{recruiting.get('jobs_extracted_count', 0)}`",
        f"- Apply flow steps: `{recruiting.get('apply_flow_steps_count', 0)}`",
        f"- Safe stop rate: `{recruiting.get('safe_stop_rate', 0.0):.2f}`",
        f"- Stop reasons: `{json.dumps(recruiting.get('stop_reason_distribution', {}), ensure_ascii=False)}`",
        "",
        "## P1 Skill Progressive Loading",
        "",
        f"- Registered skills: `{skill.get('registered_skill_count', 0)}`",
        f"- Loaded tools: `{skill.get('loaded_tool_count', 0)}`",
        f"- Skill distribution: `{json.dumps(skill.get('skill_distribution', {}), ensure_ascii=False)}`",
        "",
        "## P2 Training Export Quality",
        "",
        f"- SFT/DPO/GRPO/self-correction: `{export.get('sft_count', 0)}` / `{export.get('dpo_pair_count', 0)}` / `{export.get('grpo_group_count', 0)}` / `{export.get('self_correction_count', 0)}`",
        f"- Schema pass rate: `{export.get('schema_validation_pass_rate', 0.0):.2f}`",
        f"- Sample types: `{json.dumps(export.get('sample_type_distribution', {}), ensure_ascii=False)}`",
        "",
        "## P3 SPA-style Training Preparation",
        "",
        f"- Rollouts / steps / PPO-ready: `{spa.get('rollout_count', 0)}` / `{spa.get('step_count', 0)}` / `{spa.get('rollout_count', 0)}`",
        f"- Avg action validity: `{spa.get('avg_action_validity', 0.0):.2f}`",
        f"- Reward design: `{spa.get('reward_design', 'n/a')}`",
        "",
        "## Recruiting Replay",
        "",
        showcase["replays"]["recruiting"],
        "",
        "## Self-correction Replay",
        "",
        showcase["replays"]["self_correction_wrong_args"],
        "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build LightClaw showcase report.")
    parser.add_argument("--with-pytest", action="store_true", help="Also run smoke pytest checks.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_SHOWCASE_DIR)
    args = parser.parse_args()

    showcase = build_showcase(output_dir=args.output_dir, with_pytest=args.with_pytest)
    print(json.dumps({
        "passed": showcase["passed"],
        "showcase_json": str(args.output_dir / "showcase.json"),
        "showcase_md": str(args.output_dir / "showcase.md"),
    }, ensure_ascii=False, indent=2))
    if not showcase["passed"]:
        raise SystemExit("Showcase checks failed.")


if __name__ == "__main__":
    main()
