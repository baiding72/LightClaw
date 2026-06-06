#!/usr/bin/env python3
"""Regression eval for badcase 0001: session context vs long-term memory.

Run from the repo root:

    python -m evals.badcase_0001_context_memory

The eval uses the configured live provider from `myClaw/.env` by default.
It intentionally tests the harness end-to-end because this badcase depends on
how messages are carried across turns and how the model describes that state.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from time import perf_counter

from core.agent import create_agent_harness
from core.logger import RunLogger
from core.provider import get_provider


REPO_ROOT = Path(__file__).resolve().parents[1]
MYCLAW_ENV = REPO_ROOT / ".env"

SEED_USER_FACT = "我们正在学习 myClaw MVP 的 agent harness。"
PROBE_QUESTION = "我刚刚在学习什么？"

REQUIRED_TERMS = ("myClaw", "MVP")
FORBIDDEN_PHRASES = (
    "没有记忆",
    "无法记住",
    "无法知道",
    "没有访问之前",
    "没有之前的对话记录",
    "每次对话都是独立",
    "不能记住之前",
)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def evaluate_answer(answer: str) -> tuple[bool, list[str]]:
    failures: list[str] = []
    missing_terms = [term for term in REQUIRED_TERMS if term.lower() not in answer.lower()]
    forbidden_hits = [phrase for phrase in FORBIDDEN_PHRASES if phrase in answer]

    if missing_terms:
        failures.append(f"missing required terms: {', '.join(missing_terms)}")
    if forbidden_hits:
        failures.append(f"contains forbidden memory-denial phrase: {', '.join(forbidden_hits)}")

    return not failures, failures


def run_eval(
    provider: str | None = None,
    model: str | None = None,
    logger: RunLogger | None = None,
    iteration: int = 1,
) -> tuple[bool, str, list[str]]:
    load_env_file(MYCLAW_ENV)

    provider_name = provider or os.environ.get("MYCLAW_PROVIDER", "openai")
    model_name = model or os.environ.get("MYCLAW_MODEL")
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_API_BASE")

    llm = get_provider(
        provider_name=provider_name,  # type: ignore[arg-type]
        model=model_name,
        api_key=api_key,
        base_url=base_url,
    )
    run_logger = logger or RunLogger()
    run_logger.log_event(
        "eval_case_started",
        case_id="badcase_0001_context_memory",
        iteration=iteration,
        provider=provider_name,
        model=model_name,
        seed=SEED_USER_FACT,
        probe=PROBE_QUESTION,
        required_terms=list(REQUIRED_TERMS),
        forbidden_phrases=list(FORBIDDEN_PHRASES),
    )

    # Create Custom ReAct harness
    harness = create_agent_harness(llm)

    start = perf_counter()

    # First turn: seed the fact
    run_logger.log_event(
        "eval_user_input",
        case_id="badcase_0001_context_memory",
        iteration=iteration,
        content_preview=SEED_USER_FACT,
        turn=1,
    )
    result1 = harness.run(SEED_USER_FACT, verbose=False)

    # Second turn: probe question
    run_logger.log_event(
        "eval_user_input",
        case_id="badcase_0001_context_memory",
        iteration=iteration,
        content_preview=PROBE_QUESTION,
        turn=2,
    )
    result2 = harness.run(PROBE_QUESTION, verbose=False)

    answer = result2["answer"]
    passed, failures = evaluate_answer(answer)
    run_logger.log_event(
        "eval_case_completed",
        case_id="badcase_0001_context_memory",
        iteration=iteration,
        passed=passed,
        failures=failures,
        answer_preview=answer[:800],
        elapsed_seconds=round(perf_counter() - start, 3),
        turn1_turns=result1["turns"],
        turn2_turns=result2["turns"],
    )
    return passed, answer, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default=None, help="Provider override, e.g. openai or anthropic.")
    parser.add_argument("--model", default=None, help="Model override.")
    parser.add_argument("--repeat", type=int, default=1, help="Run the same eval N times to catch flaky failures.")
    args = parser.parse_args()

    if args.repeat < 1:
        print("ERROR: --repeat must be >= 1", file=sys.stderr)
        return 2

    logger = RunLogger()
    print("Badcase 0001: current-session context vs long-term memory")
    print(f"Seed: {SEED_USER_FACT}")
    print(f"Probe: {PROBE_QUESTION}")
    print(f"Repeat: {args.repeat}")
    print(f"Run log: {logger.path}")

    results: list[tuple[bool, str, list[str]]] = []
    for iteration in range(1, args.repeat + 1):
        try:
            result = run_eval(provider=args.provider, model=args.model, logger=logger, iteration=iteration)
        except Exception as exc:
            logger.log_event(
                "eval_case_error",
                case_id="badcase_0001_context_memory",
                iteration=iteration,
                error=str(exc),
            )
            print(f"\nITERATION {iteration}: ERROR: {exc}", file=sys.stderr)
            return 2

        passed, answer, failures = result
        results.append(result)
        status = "PASS" if passed else "FAIL"
        print(f"\nITERATION {iteration}: {status}")
        print(answer)
        if failures:
            for failure in failures:
                print(f"- {failure}")

    pass_count = sum(1 for passed, _, _ in results if passed)
    fail_count = len(results) - pass_count
    logger.log_event(
        "eval_summary",
        case_id="badcase_0001_context_memory",
        repeat=args.repeat,
        pass_count=pass_count,
        fail_count=fail_count,
    )

    print(f"\nSUMMARY: {pass_count} passed, {fail_count} failed")
    if fail_count == 0:
        print("RESULT: PASS")
        return 0

    print("RESULT: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
