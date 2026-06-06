#!/usr/bin/env python3
"""Trace regression evals for myClaw memory/tool permission behavior.

These cases intentionally start from real badcase traces. They check harness
contracts rather than model wording, so future iterations can improve the
policy/memory layer without rewriting the eval.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any
from uuid import uuid4

from core.logger import RunLogger
from interactive_turn import run_turn, safe_session_id, session_path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = REPO_ROOT / "runs"
EVALS_DIR = REPO_ROOT / "evals" / "generated"
CASES_DIR = REPO_ROOT / "evals" / "cases"
DEFAULT_SUITE = CASES_DIR / "memory_policy_badcases.json"


@dataclass(frozen=True)
class TraceCase:
    case_id: str
    title: str
    paths: tuple[str, ...]
    checker_id: str
    checker: Callable[[list[list[dict[str, Any]]]], list[str]]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.exists():
        return events
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def resolve_trace_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    if path.exists():
        return path.resolve()
    return RUNS_DIR / path


def tool_calls(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event.get("event") == "tool_call"]


def tool_names(events: list[dict[str, Any]]) -> list[str]:
    return [str(event.get("tool_name")) for event in tool_calls(events)]


def tool_args(events: list[dict[str, Any]], tool_name: str) -> list[dict[str, Any]]:
    return [
        event.get("tool_args", {})
        for event in tool_calls(events)
        if event.get("tool_name") == tool_name and isinstance(event.get("tool_args"), dict)
    ]


def turns_with_user_text(events: list[dict[str, Any]], text: str) -> set[int]:
    turns = set()
    for event in events:
        if event.get("event") not in {"user_input", "eval_user_input"}:
            continue
        if text in str(event.get("content_preview", "")):
            turn = event.get("conversation_turn") or event.get("turn")
            if isinstance(turn, int):
                turns.add(turn)
    return turns


def tools_in_turn(events: list[dict[str, Any]], turn: int) -> list[str]:
    return [
        str(event.get("tool_name"))
        for event in tool_calls(events)
        if event.get("conversation_turn") == turn
    ]


def check_case2(traces: list[list[dict[str, Any]]]) -> list[str]:
    failures: list[str] = []
    first, second = traces
    if "save_user_profile" in tool_names(first):
        failures.append("session-scoped code name was persisted to user_profile")
    names = tool_names(second)
    if "search_notes" in names and "read_user_profile" not in names:
        failures.append("cross-session retrieval searched notes but did not inspect profile")
    return failures


def check_case3(traces: list[list[dict[str, Any]]]) -> list[str]:
    first, second = traces
    if "save_user_profile" not in tool_names(first):
        return ["profile preference was not written in the seed session"]
    names = tool_names(second)
    has_injected_profile = any(event.get("event") == "memory_injected" and event.get("resource") == "memory.profile" for event in second)
    if "read_user_profile" not in names and not has_injected_profile:
        return ["new session did not read or inject user_profile before answering"]
    return []


def check_case4(traces: list[list[dict[str, Any]]]) -> list[str]:
    events = traces[0]
    failures: list[str] = []
    for turn in turns_with_user_text(events, "请记住"):
        names = tools_in_turn(events, turn)
        if not {"save_user_profile", "save_note"}.intersection(names):
            failures.append(f"turn {turn} requested memory write but no create/update memory tool ran")
    return failures


def check_case5(traces: list[list[dict[str, Any]]]) -> list[str]:
    names = tool_names(traces[0])
    edit_actions = [args for args in tool_args(traces[0], "save_note") if str(args.get("action", "")).lower() == "edit"]
    if names.count("save_note") > 1 and not edit_actions:
        return ["note revision created another note instead of using save_note(action=edit)"]
    return []


def check_case6(traces: list[list[dict[str, Any]]]) -> list[str]:
    names = tool_names(traces[0])
    if "web_search" in names or "read_url" in names:
        return ["local myClaw harness question used external web source instead of local memory/project sources"]
    return []


def check_case7(traces: list[list[dict[str, Any]]]) -> list[str]:
    names = tool_names(traces[0])
    failures: list[str] = []
    if "read_office_file" not in names:
        failures.append("memory_design.md request did not read office file")
    if "save_user_profile" not in names:
        failures.append("explicit answer preference was not written to profile")
    return failures


def check_case8(traces: list[list[dict[str, Any]]]) -> list[str]:
    events = traces[0]
    failures: list[str] = []
    temp_turns = turns_with_user_text(events, "临时偏好")
    for turn in temp_turns:
        if "save_user_profile" in tools_in_turn(events, turn):
            failures.append(f"turn {turn} persisted temporary preference to profile")

    for args in tool_args(events, "save_user_profile"):
        content = str(args.get("new_content", ""))
        if not content.strip():
            failures.append("profile delete/update used empty content, risking whole-profile wipe")

    for args in tool_args(events, "web_search"):
        max_results = args.get("max_results")
        if max_results is not None and not isinstance(max_results, int):
            failures.append("web_search max_results was not an integer before execution")
    return failures


CHECKERS: dict[str, Callable[[list[list[dict[str, Any]]]], list[str]]] = {
    "scope_consistency": check_case2,
    "profile_injection": check_case3,
    "explicit_memory_write": check_case4,
    "note_update": check_case5,
    "source_routing": check_case6,
    "file_and_profile": check_case7,
    "temporary_preference_and_schema": check_case8,
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"memory/policy eval suite not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"memory/policy eval suite must be a JSON object: {path}")
    return data


def suite_file_for_name(suite: str) -> Path:
    path = Path(suite)
    if path.exists():
        return path
    if path.suffix == ".json":
        return CASES_DIR / path.name
    return CASES_DIR / f"{suite}.json"


def trace_case_from_spec(raw_case: dict[str, Any]) -> TraceCase:
    checker_id = str(raw_case.get("checker", ""))
    checker = CHECKERS.get(checker_id)
    if checker is None:
        raise ValueError(f"unknown memory/policy checker: {checker_id!r}")

    paths = raw_case.get("trace_paths", [])
    if not isinstance(paths, list) or not paths:
        raise ValueError(f"{raw_case.get('case_id', '<unknown>')}: trace_paths must be a non-empty list")

    return TraceCase(
        case_id=str(raw_case["case_id"]),
        title=str(raw_case.get("title", raw_case["case_id"])),
        paths=tuple(str(path) for path in paths),
        checker_id=checker_id,
        checker=checker,
    )


def load_trace_cases(suite_data: dict[str, Any], case_filter: str | None = None) -> list[TraceCase]:
    cases = [
        trace_case_from_spec(raw_case)
        for raw_case in suite_data.get("cases", [])
        if isinstance(raw_case, dict) and (not case_filter or case_filter in str(raw_case.get("case_id", "")))
    ]
    if not cases:
        raise ValueError(f"no memory/policy eval cases selected for suite {suite_data.get('suite_id', '<unknown>')!r}")
    return cases


def create_eval_spec_from_trace(path: Path, title: str | None = None) -> Path:
    events = load_jsonl(path)
    user_inputs = [
        event
        for event in events
        if event.get("event") in {"user_input", "eval_user_input"}
    ]
    case_id = f"trace_replay_{path.stem}"
    spec = {
        "suite_id": case_id,
        "title": title or f"Trace replay: {path.stem}",
        "description": "Generated from a historical JSONL trace. Replays extracted user inputs in a fresh session.",
        "source_trace": str(path),
        "generated_from_trace": True,
        "cases": [
            {
                "case_id": case_id,
                "title": title or path.stem,
                "source_trace": str(path),
                "turns": [
                    {
                        "turn": event.get("conversation_turn") or event.get("turn") or index + 1,
                        "input": event.get("content") or event.get("content_preview", ""),
                        "assertions": {
                            "required_events": ["user_input", "llm_input", "ai_message", "turn_completed"]
                        },
                    }
                    for index, event in enumerate(user_inputs)
                ],
            }
        ],
        "suggested_assertions": [
            "add required_tools/forbidden_tools for tool routing contracts",
            "add answer_contains/answer_not_contains for visible behavior",
            "add required_tool_order for multi-step ReAct behavior",
        ],
    }
    EVALS_DIR.mkdir(parents=True, exist_ok=True)
    output = EVALS_DIR / f"{path.stem}.eval.json"
    output.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def start_eval_from_trace(path: Path) -> int:
    """Replay a trace as a fresh interactive session and write an eval run."""
    events = load_jsonl(path)
    output = create_eval_spec_from_trace(path)
    logger = RunLogger()
    case_id = f"trace_eval_{path.stem}"
    user_inputs = [
        event
        for event in events
        if event.get("event") in {"user_input", "eval_user_input"}
    ]
    failures: list[str] = []
    if not events:
        failures.append(f"missing or empty trace: {path}")
    if not user_inputs:
        failures.append("trace has no user_input/eval_user_input events")

    eval_session_id = safe_session_id(f"eval-{path.stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}")
    transcript_path = session_path(eval_session_id)
    if transcript_path.exists():
        transcript_path.unlink()

    print("myClaw trace eval")
    print(f"Source trace: {path}")
    print(f"Eval spec: {output}")
    print(f"Eval log: {logger.path}")

    logger.log_event(
        "eval_suite_started",
        case_id=case_id,
        suite_id=case_id,
        title=path.stem,
        source_trace=str(path),
        generated_spec=str(output),
        case_count=1,
        runner="trace_replay",
    )
    logger.log_event(
        "eval_case_started",
        case_id=case_id,
        suite_id=case_id,
        title=path.stem,
        source_trace=str(path),
        generated_spec=str(output),
        replay_session_id=eval_session_id,
        turn_count=len(user_inputs),
    )

    replay_run_path = ""
    replay_answers: list[str] = []
    for index, event in enumerate(user_inputs, start=1):
        user_input = str(event.get("content") or event.get("content_preview") or "")
        logger.log_event(
            "eval_user_input",
            case_id=case_id,
            suite_id=case_id,
            turn=event.get("conversation_turn") or event.get("turn") or index,
            content_preview=user_input[:500],
        )
        if failures:
            continue
        try:
            result = run_turn(eval_session_id, user_input)
        except Exception as exc:
            failures.append(f"turn {index} replay failed: {type(exc).__name__}: {exc}")
            logger.log_event(
                "eval_case_error",
                case_id=case_id,
                suite_id=case_id,
                turn=index,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            break

        replay_run_path = str(result.get("run_path", replay_run_path))
        answer = str(result.get("answer", ""))
        replay_answers.append(answer)
        logger.log_event(
            "eval_turn_replayed",
            case_id=case_id,
            suite_id=case_id,
            turn=index,
            replay_session_id=eval_session_id,
            replay_run_path=replay_run_path,
            answer_preview=answer[:800],
            harness_turns=result.get("turns"),
        )

    passed = not failures
    logger.log_event(
        "eval_case_completed",
        case_id=case_id,
        suite_id=case_id,
        passed=passed,
        failures=failures,
        source_event_count=len(events),
        generated_spec=str(output),
        replay_session_id=eval_session_id,
        replay_run_path=replay_run_path,
        trace_paths=[str(path), replay_run_path] if replay_run_path else [str(path)],
        replay_turn_count=len(replay_answers),
    )
    logger.log_event(
        "eval_summary",
        case_id=case_id,
        suite_id=case_id,
        pass_count=1 if passed else 0,
        fail_count=0 if passed else 1,
        replay_run_path=replay_run_path,
    )
    if replay_run_path:
        print(f"Run log: {replay_run_path}")
    print("RESULT: PASS" if passed else "RESULT: FAIL")
    for failure in failures:
        print(f"- {failure}")
    return 0 if passed else 1


def run_trace_suite(
    suite_data: dict[str, Any],
    suite_path: Path | None = None,
    case_filter: str | None = None,
) -> int:
    suite_id = str(suite_data.get("suite_id", "memory_policy_badcases"))
    try:
        selected = load_trace_cases(suite_data, case_filter)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    logger = RunLogger(run_id=f"trace-eval-{suite_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}")
    pass_count = 0
    fail_count = 0

    print("myClaw memory/tool policy trace regression")
    print(f"Suite: {suite_id}")
    if suite_path:
        print(f"Spec: {suite_path}")
    print(f"Run log: {logger.path}")

    logger.log_event(
        "eval_suite_started",
        case_id=suite_id,
        suite_id=suite_id,
        title=suite_data.get("title", suite_id),
        description=suite_data.get("description", ""),
        spec_path=str(suite_path) if suite_path else None,
        case_count=len(selected),
        runner="trace_regression",
    )

    for case in selected:
        logger.log_event(
            "eval_case_started",
            case_id=case.case_id,
            suite_id=suite_id,
            title=case.title,
            checker=case.checker_id,
            trace_paths=list(case.paths),
        )
        resolved_paths = [resolve_trace_path(path) for path in case.paths]
        traces = [load_jsonl(path) for path in resolved_paths]
        missing = [str(path) for path, events in zip(resolved_paths, traces) if not events]
        failures = [f"missing or empty trace: {path}" for path in missing]
        if not failures:
            failures = case.checker(traces)
        passed = not failures
        pass_count += int(passed)
        fail_count += int(not passed)
        logger.log_event(
            "eval_case_completed",
            case_id=case.case_id,
            suite_id=suite_id,
            title=case.title,
            checker=case.checker_id,
            passed=passed,
            failures=failures,
            trace_paths=[str(path) for path in resolved_paths],
            source_event_counts=[len(events) for events in traces],
        )
        print(f"\n{case.case_id}: {'PASS' if passed else 'FAIL'}")
        for failure in failures:
            print(f"- {failure}")

    logger.log_event(
        "eval_summary",
        case_id=suite_id,
        suite_id=suite_id,
        pass_count=pass_count,
        fail_count=fail_count,
        spec_path=str(suite_path) if suite_path else None,
    )
    print(f"\nSUMMARY: {pass_count} passed, {fail_count} failed")
    print("RESULT: PASS" if fail_count == 0 else "RESULT: FAIL")
    return 0 if fail_count == 0 else 1


def run_cases(case_filter: str | None = None, suite: str | None = None) -> int:
    try:
        suite_path = suite_file_for_name(suite) if suite else DEFAULT_SUITE
        suite_data = load_json(suite_path)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    return run_trace_suite(suite_data, suite_path=suite_path, case_filter=case_filter)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default=None, help="Trace regression suite id or JSON file path.")
    parser.add_argument("--case", default=None, help="Run only case ids containing this text.")
    parser.add_argument("--from-trace", default=None, help="Generate an eval spec JSON from a trace path.")
    parser.add_argument("--start-from-trace", default=None, help="Generate an eval spec and write an eval run from a trace path.")
    args = parser.parse_args()

    if args.start_from_trace:
        return start_eval_from_trace(resolve_trace_path(args.start_from_trace))

    if args.from_trace:
        path = resolve_trace_path(args.from_trace)
        output = create_eval_spec_from_trace(path)
        print(f"Generated eval spec: {output}")
        return 0

    return run_cases(args.case, suite=args.suite)


if __name__ == "__main__":
    raise SystemExit(main())
