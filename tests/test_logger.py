"""Tests for the myClaw JSONL harness logger."""

import json

from langchain_core.messages import AIMessage, HumanMessage

from core.logger import RunLogger, summarize_messages


def test_run_logger_writes_jsonl_event(tmp_path):
    logger = RunLogger(run_id="test-run", runs_dir=tmp_path)

    logger.log_event("example_event", value=123, text="hello")

    lines = logger.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["run_id"] == "test-run"
    assert record["event"] == "example_event"
    assert record["value"] == 123
    assert record["text"] == "hello"
    assert "ts" in record


def test_summarize_messages_keeps_types_and_short_previews():
    messages = [
        HumanMessage(content="hello"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "calculator",
                    "args": {"expression": "1 + 1"},
                }
            ],
        ),
    ]

    summary = summarize_messages(messages)

    assert summary[0]["type"] == "HumanMessage"
    assert summary[0]["content_preview"] == "hello"
    assert summary[1]["type"] == "AIMessage"
    assert summary[1]["tool_calls"][0]["name"] == "calculator"
