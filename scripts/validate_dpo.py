"""
校验 DPO 数据集

用法：
    cd /Users/baiding/Desktop/LightClaw
    uv run python scripts/validate_dpo.py
"""
from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path

from pydantic import ValidationError


RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _print_header(title: str) -> None:
    print(f"{BOLD}{CYAN}{title}{RESET}")


def _format_error(line_no: int, field_name: str, error: Exception) -> str:
    return f"{RED}Line {line_no} [{field_name}] -> {type(error).__name__}: {error}{RESET}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate DPO dataset samples for AgentDecision compatibility.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail fast on the first invalid sample and exit with status code 1.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "backend"))

    from app.schemas.gui_agent import AgentDecision

    dataset_path = repo_root / "backend" / "data" / "dpo_dataset.jsonl"

    _print_header("DPO Dataset Validation")
    print(f"Dataset: {dataset_path}")

    if not dataset_path.exists():
        print(f"{YELLOW}Dataset file not found. Nothing to validate.{RESET}")
        return 0

    total = 0
    passed = 0
    failed = 0
    errors: list[str] = []

    with dataset_path.open("r", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue

            total += 1
            try:
                sample = json.loads(line)
                chosen_raw = sample["chosen"]
                rejected_raw = sample["rejected"]

                chosen_obj = json.loads(chosen_raw) if isinstance(chosen_raw, str) else chosen_raw
                rejected_obj = json.loads(rejected_raw) if isinstance(rejected_raw, str) else rejected_raw

                AgentDecision.model_validate(chosen_obj)
                AgentDecision.model_validate(rejected_obj)
                passed += 1
            except (json.JSONDecodeError, KeyError, ValidationError, TypeError, ValueError) as exc:
                failed += 1
                field_name = "sample"
                if isinstance(exc, KeyError):
                    field_name = str(exc)
                elif isinstance(exc, ValidationError):
                    field_name = "AgentDecision"
                formatted_error = _format_error(line_no, field_name, exc)
                errors.append(formatted_error)
                if args.strict:
                    print()
                    _print_header("Validation Errors")
                    print(formatted_error)
                    print()
                    print(f"{RED}Strict mode enabled. Validation stopped at first invalid sample.{RESET}")
                    sys.exit(1)

    print()
    print(f"{BOLD}Total Samples:{RESET} {total}")
    print(f"{GREEN}Passed:{RESET} {passed}")
    print(f"{RED if failed else GREEN}Failed:{RESET} {failed}")

    if errors:
        print()
        _print_header("Validation Errors")
        for error in errors:
            print(error)
        return 1

    print()
    print(f"{GREEN}All DPO samples are valid.{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
