#!/usr/bin/env python3
"""Run LightClaw evaluation.

Default mode is deterministic and requires no LLM API key.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.eval.deterministic import build_deterministic_evaluation
from app.eval.reports import ReportGenerator
from app.eval.runner import EvaluationRunner


async def run_live(eval_name: str):
    runner = EvaluationRunner()
    return await runner.run_evaluation(eval_name=eval_name)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run LightClaw evaluation.")
    parser.add_argument("--mode", choices=["deterministic", "live"], default="deterministic")
    parser.add_argument("--eval-name", default=None)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    eval_name = args.eval_name or f"{args.mode}_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    result = (
        await run_live(eval_name)
        if args.mode == "live"
        else build_deterministic_evaluation(eval_name)
    )

    settings = get_settings()
    output_dir = Path(args.output_dir or Path(settings.data_dir) / "eval_reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    latest_json = output_dir / "latest.json"
    latest_md = output_dir / "latest.md"

    payload = result.model_dump(mode="json")
    payload["mode"] = args.mode
    payload["source"] = "deterministic_fixture" if args.mode == "deterministic" else "live_agent"
    latest_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report = ReportGenerator(output_dir=str(output_dir)).generate_markdown_report(result)
    latest_md.write_text(report, encoding="utf-8")

    print("=" * 60)
    print(f"LightClaw Evaluation ({args.mode})")
    print("=" * 60)
    print(f"Task success rate: {result.metrics.task_success_rate:.2%}")
    print(f"Tool execution success rate: {result.metrics.tool_execution_success_rate:.2%}")
    print(f"Recovery rate: {result.metrics.recovery_rate:.2%}")
    print(f"Invalid tool call rate: {result.metrics.invalid_tool_call_rate:.2%}")
    print(f"Wrong args rate: {result.metrics.wrong_args_rate:.2%}")
    print(f"Policy violation rate: {result.metrics.policy_violation_rate:.2%}")
    print(f"GUI grounding accuracy: {result.metrics.gui_action_accuracy:.2%}")
    print(f"Average steps: {result.metrics.avg_steps:.2f}")
    print(f"Average latency: {result.metrics.avg_latency_ms:.0f}ms")
    print(f"Report: {latest_json}")


if __name__ == "__main__":
    asyncio.run(main())
