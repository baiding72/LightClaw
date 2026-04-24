#!/usr/bin/env python3
"""Run the reproducibility checks for LightClaw without requiring an LLM API key."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
DEFAULT_EXPORT_DIR = BACKEND / "data" / "training_exports" / "latest"
DEFAULT_REPLAY_PATH = BACKEND / "data" / "eval_reports" / "replay_wrong_args.md"


@dataclass
class CheckResult:
    name: str
    passed: bool
    command: list[str]
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


def run_command(command: list[str], *, cwd: Path) -> CheckResult:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            text=True,
            capture_output=True,
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(command[2] if len(command) > 2 else command[0], False, command, error=str(exc))

    return CheckResult(
        name=" ".join(command[:3]),
        passed=completed.returncode == 0,
        command=command,
        stdout=completed.stdout,
        stderr=completed.stderr,
        error=None if completed.returncode == 0 else f"exit_code={completed.returncode}",
    )


def run_all_checks(*, with_pytest: bool = False) -> dict:
    DEFAULT_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_REPLAY_PATH.parent.mkdir(parents=True, exist_ok=True)

    checks: list[CheckResult] = []
    checks.append(run_command(["uv", "run", "python", "../scripts/run_eval.py", "--mode", "deterministic"], cwd=BACKEND))
    checks.append(run_command([
        "uv",
        "run",
        "python",
        "../scripts/export_training_data.py",
        "--fixtures",
        "--with-data-card",
        "--output-dir",
        str(DEFAULT_EXPORT_DIR),
    ], cwd=BACKEND))

    replay = run_command([
        "uv",
        "run",
        "python",
        "../scripts/replay_trace.py",
        "--fixture-case",
        "wrong_args",
    ], cwd=BACKEND)
    if replay.passed:
        DEFAULT_REPLAY_PATH.write_text(replay.stdout, encoding="utf-8")
    checks.append(replay)

    if with_pytest:
        checks.append(run_command([
            "uv",
            "run",
            "--with",
            "pytest",
            "--with",
            "pytest-asyncio",
            "pytest",
            "tests/test_self_correction.py",
            "tests/test_eval_report.py",
            "tests/test_training_data_quality.py",
        ], cwd=BACKEND))

    summary = {
        "passed": all(check.passed for check in checks),
        "eval_report_path": str(BACKEND / "data" / "eval_reports" / "latest.json"),
        "training_export_path": str(DEFAULT_EXPORT_DIR),
        "data_card_path": str(DEFAULT_EXPORT_DIR / "data_card.json"),
        "replay_output_path": str(DEFAULT_REPLAY_PATH),
        "checks": [
            {
                "name": check.name,
                "passed": check.passed,
                "command": " ".join(check.command),
                "error": check.error,
                "stderr": check.stderr.strip()[-500:] if check.stderr else "",
            }
            for check in checks
        ],
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all LightClaw reproducibility checks.")
    parser.add_argument("--with-pytest", action="store_true", help="Also run smoke pytest checks.")
    args = parser.parse_args()

    summary = run_all_checks(with_pytest=args.with_pytest)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["passed"]:
        failed = [item for item in summary["checks"] if not item["passed"]]
        raise SystemExit(f"One or more checks failed: {failed}")


if __name__ == "__main__":
    main()
