from pathlib import Path

from evals.agent_eval_runner import assert_turn, case_file_for_suite


def test_assert_turn_checks_tool_args_and_negative_text():
    events = [
        {"event": "user_input", "conversation_turn": 1},
        {"event": "llm_input", "conversation_turn": 1},
        {
            "event": "tool_call",
            "conversation_turn": 1,
            "tool_name": "write_office_file",
            "tool_args": {"path": "test.py", "content": "print('hello myclaw')"},
        },
        {
            "event": "tool_result",
            "conversation_turn": 1,
            "tool_name": "write_office_file",
            "tool_result": "wrote test.py",
        },
        {"event": "ai_message", "conversation_turn": 1},
        {"event": "turn_completed", "conversation_turn": 1},
    ]

    failures = assert_turn(
        case_id="file_create",
        turn_index=1,
        answer="已创建 test.py",
        events=events,
        assertions={
            "required_events": ["user_input", "llm_input", "tool_call", "tool_result", "ai_message", "turn_completed"],
            "required_tools": ["write_office_file"],
            "required_tool_args": [{"tool": "write_office_file", "args": {"path": "test.py"}}],
            "required_tool_arg_contains": [{"tool": "write_office_file", "arg": "content", "contains": "hello myclaw"}],
            "answer_not_contains": ["失败"],
            "tool_result_not_contains": ["Error"],
            "min_tool_calls": 1,
            "max_tool_calls": 1,
        },
    )

    assert failures == []


def test_assert_turn_reports_missing_arg_match():
    events = [
        {
            "event": "tool_call",
            "conversation_turn": 1,
            "tool_name": "calculator",
            "tool_args": {"expression": "25*48"},
        }
    ]

    failures = assert_turn(
        case_id="calc_basic",
        turn_index=1,
        answer="1200",
        events=events,
        assertions={
            "required_tool_args": [{"tool": "calculator", "args": {"expression": "25 * 48"}}],
        },
    )

    assert any("no calculator call matched args" in failure for failure in failures)


def test_case_file_for_suite_resolves_named_suite():
    path = case_file_for_suite("basic_tasks")

    assert path == Path(__file__).resolve().parents[1] / "evals" / "cases" / "basic_tasks.json"
