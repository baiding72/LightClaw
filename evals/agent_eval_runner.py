#!/usr/bin/env python3
"""Run agent-level eval suites from JSON case files.

The runner starts real myClaw interactive sessions through `run_turn`, then
checks the generated trace. It writes its own eval JSONL log under
`runs`, so the Mac client can display pass/fail results directly.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.logger import RunLogger
from interactive_turn import run_turn, safe_session_id, session_path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = REPO_ROOT / "runs"
CASES_DIR = REPO_ROOT / "evals" / "cases"


@dataclass(frozen=True)
class TurnResult:
    turn_index: int
    input: str
    answer: str
    replay_run_path: str
    replay_events: list[dict[str, Any]]
    failures: list[str]


@dataclass
class MemorySnapshot:
    files: dict[Path, str | None]

    def restore(self) -> None:
        for path, content in self.files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(content, encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"eval suite not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"eval suite must be a JSON object: {path}")
    return data


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    path = Path(path)
    if not path.exists():
        return events
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def memory_files() -> list[Path]:
    from core.config import MEMORY_DIR

    return [MEMORY_DIR / "profile.md", MEMORY_DIR / "MEMORY.md"]


def snapshot_memory() -> MemorySnapshot:
    files: dict[Path, str | None] = {}
    for path in memory_files():
        files[path] = path.read_text(encoding="utf-8") if path.exists() else None
    return MemorySnapshot(files=files)


def apply_case_setup(case: dict[str, Any]) -> MemorySnapshot | None:
    setup = case.get("setup") or {}
    if not isinstance(setup, dict) or (
        not setup.get("clear_memory")
        and "profile" not in setup
        and "project_memory" not in setup
    ):
        return None
    snapshot = snapshot_memory()
    files = memory_files()
    if setup.get("clear_memory"):
        for path in files:
            path.unlink(missing_ok=True)
    profile = setup.get("profile")
    if isinstance(profile, str):
        files[0].parent.mkdir(parents=True, exist_ok=True)
        files[0].write_text(profile, encoding="utf-8")
    project_memory = setup.get("project_memory")
    if isinstance(project_memory, str):
        files[1].parent.mkdir(parents=True, exist_ok=True)
        files[1].write_text(project_memory, encoding="utf-8")
    return snapshot


def case_file_for_suite(suite: str) -> Path:
    path = Path(suite)
    if path.exists():
        return path
    if path.suffix != ".json":
        path = CASES_DIR / f"{suite}.json"
    else:
        path = CASES_DIR / path.name
    return path


def event_names(events: list[dict[str, Any]]) -> list[str]:
    return [str(event.get("event", "")) for event in events]


def tool_calls_for_turn(events: list[dict[str, Any]], conversation_turn: int) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if event.get("event") == "tool_call" and event.get("conversation_turn") == conversation_turn
    ]


def tool_results_for_turn(events: list[dict[str, Any]], conversation_turn: int) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if event.get("event") == "tool_result" and event.get("conversation_turn") == conversation_turn
    ]


def _contains(haystack: Any, needle: Any) -> bool:
    return str(needle).lower() in str(haystack).lower()


def _tool_args_match(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    for key, expected_value in expected.items():
        if key not in actual:
            return False
        if actual[key] != expected_value:
            return False
    return True


def assert_turn(
    *,
    case_id: str,
    turn_index: int,
    answer: str,
    events: list[dict[str, Any]],
    assertions: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    names = event_names(events)
    tool_events = tool_calls_for_turn(events, turn_index)
    tool_names = [str(event.get("tool_name", "")) for event in tool_events]
    tool_result_text = "\n".join(
        str(event.get("tool_result") or event.get("result") or "")
        for event in tool_results_for_turn(events, turn_index)
    )

    for required_event in assertions.get("required_events", []):
        if required_event not in names:
            failures.append(f"turn {turn_index}: missing required event {required_event}")

    for required_tool in assertions.get("required_tools", []):
        if required_tool not in tool_names:
            failures.append(
                f"turn {turn_index}: missing required tool {required_tool}; saw {tool_names or 'none'}"
            )

    for group in assertions.get("one_of_required_tools", []):
        if not any(tool in tool_names for tool in group):
            failures.append(
                f"turn {turn_index}: expected one of tools {group}; saw {tool_names or 'none'}"
            )

    for forbidden_tool in assertions.get("forbidden_tools", []):
        if forbidden_tool in tool_names:
            failures.append(f"turn {turn_index}: forbidden tool was used: {forbidden_tool}")

    min_tool_calls = assertions.get("min_tool_calls")
    if isinstance(min_tool_calls, int) and len(tool_events) < min_tool_calls:
        failures.append(
            f"turn {turn_index}: expected at least {min_tool_calls} tool calls; saw {len(tool_events)}"
        )

    max_tool_calls = assertions.get("max_tool_calls")
    if isinstance(max_tool_calls, int) and len(tool_events) > max_tool_calls:
        failures.append(
            f"turn {turn_index}: expected at most {max_tool_calls} tool calls; saw {len(tool_events)}"
        )

    for needle in assertions.get("answer_contains", []):
        if not _contains(answer, needle):
            failures.append(f"turn {turn_index}: answer missing expected text {needle!r}")

    for needle in assertions.get("answer_not_contains", []):
        if _contains(answer, needle):
            failures.append(f"turn {turn_index}: answer contains forbidden text {needle!r}")

    for needle in assertions.get("tool_result_contains", []):
        if not _contains(tool_result_text, needle):
            failures.append(f"turn {turn_index}: tool result missing expected text {needle!r}")

    for needle in assertions.get("tool_result_not_contains", []):
        if _contains(tool_result_text, needle):
            failures.append(f"turn {turn_index}: tool result contains forbidden text {needle!r}")

    for item in assertions.get("required_tool_args", []):
        tool_name = str(item.get("tool", ""))
        expected_args = item.get("args", {})
        if not isinstance(expected_args, dict):
            failures.append(f"turn {turn_index}: required_tool_args for {tool_name} must be an object")
            continue
        matching_events = [event for event in tool_events if event.get("tool_name") == tool_name]
        if not any(_tool_args_match(event.get("tool_args", {}), expected_args) for event in matching_events):
            failures.append(
                f"turn {turn_index}: no {tool_name} call matched args {expected_args}; "
                f"saw {[event.get('tool_args', {}) for event in matching_events] or 'none'}"
            )

    for item in assertions.get("required_tool_arg_contains", []):
        tool_name = str(item.get("tool", ""))
        arg_name = str(item.get("arg", ""))
        needle = item.get("contains", "")
        matching_events = [event for event in tool_events if event.get("tool_name") == tool_name]
        if not any(_contains(event.get("tool_args", {}).get(arg_name, ""), needle) for event in matching_events):
            failures.append(
                f"turn {turn_index}: no {tool_name}.{arg_name} argument contained {needle!r}; "
                f"saw {[event.get('tool_args', {}).get(arg_name) for event in matching_events] or 'none'}"
            )

    expected_order = assertions.get("required_tool_order", [])
    if expected_order:
        cursor = 0
        for tool in tool_names:
            if cursor < len(expected_order) and tool == expected_order[cursor]:
                cursor += 1
        if cursor != len(expected_order):
            failures.append(
                f"turn {turn_index}: required tool order {expected_order} not satisfied; saw {tool_names}"
            )

    return [f"{case_id}: {failure}" for failure in failures]


def run_case(case: dict[str, Any], suite_id: str, logger: RunLogger) -> tuple[bool, list[str], str]:
    case_id = str(case["case_id"])
    title = str(case.get("title", case_id))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    eval_session_id = safe_session_id(f"agent-eval-{suite_id}-{case_id}-{stamp}-{uuid4().hex[:6]}")
    transcript_path = session_path(eval_session_id)
    if transcript_path.exists():
        transcript_path.unlink()

    logger.log_event(
        "eval_case_started",
        case_id=case_id,
        suite_id=suite_id,
        title=title,
        replay_session_id=eval_session_id,
        turn_count=len(case.get("turns", [])),
    )

    failures: list[str] = []
    replay_run_path = ""
    turn_results: list[TurnResult] = []
    memory_snapshot = apply_case_setup(case)

    try:
        for turn_index, turn in enumerate(case.get("turns", []), start=1):
            user_input = str(turn.get("input", ""))
            logger.log_event(
                "eval_user_input",
                case_id=case_id,
                suite_id=suite_id,
                turn=turn_index,
                replay_session_id=eval_session_id,
                content_preview=user_input[:500],
            )

            try:
                result = run_turn(eval_session_id, user_input)
            except Exception as exc:
                failure = f"{case_id}: turn {turn_index} replay failed: {type(exc).__name__}: {exc}"
                failures.append(failure)
                logger.log_event(
                    "eval_case_error",
                    case_id=case_id,
                    suite_id=suite_id,
                    turn=turn_index,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                break

            replay_run_path = str(result.get("run_path", replay_run_path))
            answer = str(result.get("answer", ""))
            events = load_jsonl(replay_run_path)
            turn_failures = assert_turn(
                case_id=case_id,
                turn_index=turn_index,
                answer=answer,
                events=events,
                assertions=turn.get("assertions", {}),
            )
            failures.extend(turn_failures)
            turn_results.append(
                TurnResult(
                    turn_index=turn_index,
                    input=user_input,
                    answer=answer,
                    replay_run_path=replay_run_path,
                    replay_events=events,
                    failures=turn_failures,
                )
            )

            logger.log_event(
                "eval_turn_replayed",
                case_id=case_id,
                suite_id=suite_id,
                turn=turn_index,
                replay_session_id=eval_session_id,
                replay_run_path=replay_run_path,
                answer_preview=answer[:800],
                harness_turns=result.get("turns"),
                passed=not turn_failures,
                failures=turn_failures,
                tool_names=[
                    event.get("tool_name")
                    for event in tool_calls_for_turn(events, turn_index)
                ],
            )
    finally:
        if memory_snapshot:
            memory_snapshot.restore()

    passed = not failures
    logger.log_event(
        "eval_case_completed",
        case_id=case_id,
        suite_id=suite_id,
        title=title,
        passed=passed,
        failures=failures,
        replay_session_id=eval_session_id,
        replay_run_path=replay_run_path,
        replay_turn_count=len(turn_results),
    )
    return passed, failures, replay_run_path


def run_suite(suite: str, case_filter: str | None = None) -> int:
    try:
        suite_path = case_file_for_suite(suite)
        data = load_json(suite_path)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2

    suite_id = str(data.get("suite_id", suite_path.stem))
    if data.get("runner") == "trace_regression":
        from evals.memory_policy_cases import run_trace_suite

        return run_trace_suite(data, suite_path=suite_path, case_filter=case_filter)

    policy_mode = str(data.get("policy_mode", "")).strip()
    cases = [
        case
        for case in data.get("cases", [])
        if not case_filter or case_filter in str(case.get("case_id", ""))
    ]
    if not cases:
        print(f"ERROR: no eval cases selected for suite {suite_id!r}")
        return 2
    logger = RunLogger(run_id=f"agent-eval-{suite_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}")

    print("myClaw agent eval")
    print(f"Suite: {suite_id}")
    print(f"Spec: {suite_path}")
    print(f"Eval log: {logger.path}")

    logger.log_event(
        "eval_suite_started",
        case_id=suite_id,
        suite_id=suite_id,
        title=data.get("title", suite_id),
        spec_path=str(suite_path),
        case_count=len(cases),
        description=data.get("description", ""),
        policy_mode=policy_mode or None,
    )

    previous_policy_mode = os.environ.get("MYCLAW_POLICY_MODE")
    if policy_mode:
        os.environ["MYCLAW_POLICY_MODE"] = policy_mode

    pass_count = 0
    fail_count = 0
    last_replay_run_path = ""
    try:
        for case in cases:
            passed, failures, replay_run_path = run_case(case, suite_id, logger)
            pass_count += int(passed)
            fail_count += int(not passed)
            last_replay_run_path = replay_run_path or last_replay_run_path
            status = "PASS" if passed else "FAIL"
            print(f"\n{case.get('case_id')}: {status}")
            for failure in failures:
                print(f"- {failure}")
    finally:
        if previous_policy_mode is None:
            os.environ.pop("MYCLAW_POLICY_MODE", None)
        else:
            os.environ["MYCLAW_POLICY_MODE"] = previous_policy_mode

    logger.log_event(
        "eval_summary",
        case_id=suite_id,
        suite_id=suite_id,
        pass_count=pass_count,
        fail_count=fail_count,
        spec_path=str(suite_path),
        replay_run_path=last_replay_run_path,
    )
    print(f"\nSUMMARY: {pass_count} passed, {fail_count} failed")
    print(f"Run log: {logger.path}")
    print("RESULT: PASS" if fail_count == 0 else "RESULT: FAIL")
    return 0 if fail_count == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="basic_tasks", help="Suite id or JSON file path.")
    parser.add_argument("--case", default=None, help="Run only case ids containing this text.")
    args = parser.parse_args()
    return run_suite(args.suite, args.case)


if __name__ == "__main__":
    raise SystemExit(main())
