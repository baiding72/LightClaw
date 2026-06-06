"""Tests migrated from CyberClaw heartbeat task scheduling behavior."""

from __future__ import annotations

import json
from datetime import datetime, timedelta


def test_check_due_tasks_once_no_file(tmp_path, monkeypatch):
    import core.heartbeat as heartbeat
    import core.tools.builtins as builtins

    monkeypatch.setattr(builtins, "TASKS_FILE", tmp_path / "missing.json")

    assert heartbeat.check_due_tasks_once() == []


def test_check_due_tasks_once_triggers_and_removes_one_shot(tmp_path, monkeypatch):
    import core.heartbeat as heartbeat
    import core.tools.builtins as builtins

    task_file = tmp_path / "tasks.json"
    monkeypatch.setattr(builtins, "TASKS_FILE", task_file)
    task_file.write_text(
        json.dumps(
            [
                {
                    "id": "task1",
                    "target_time": (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S"),
                    "description": "due task",
                    "repeat": None,
                    "repeat_count": None,
                }
            ]
        ),
        encoding="utf-8",
    )

    triggered = heartbeat.check_due_tasks_once()
    pending = json.loads(task_file.read_text(encoding="utf-8"))

    assert [task["id"] for task in triggered] == ["task1"]
    assert pending == []


def test_check_due_tasks_once_keeps_future_task(tmp_path, monkeypatch):
    import core.heartbeat as heartbeat
    import core.tools.builtins as builtins

    task_file = tmp_path / "tasks.json"
    monkeypatch.setattr(builtins, "TASKS_FILE", task_file)
    future_time = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    task_file.write_text(
        json.dumps(
            [
                {
                    "id": "future",
                    "target_time": future_time,
                    "description": "future task",
                    "repeat": None,
                    "repeat_count": None,
                }
            ]
        ),
        encoding="utf-8",
    )

    assert heartbeat.check_due_tasks_once() == []
    pending = json.loads(task_file.read_text(encoding="utf-8"))
    assert pending[0]["id"] == "future"


def test_check_due_tasks_once_reschedules_repeating_task(tmp_path, monkeypatch):
    import core.heartbeat as heartbeat
    import core.tools.builtins as builtins

    task_file = tmp_path / "tasks.json"
    monkeypatch.setattr(builtins, "TASKS_FILE", task_file)
    past_dt = datetime.now() - timedelta(minutes=5)
    task_file.write_text(
        json.dumps(
            [
                {
                    "id": "repeat",
                    "target_time": past_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "description": "daily task",
                    "repeat": "daily",
                    "repeat_count": 3,
                }
            ]
        ),
        encoding="utf-8",
    )

    triggered = heartbeat.check_due_tasks_once()
    pending = json.loads(task_file.read_text(encoding="utf-8"))

    assert triggered[0]["id"] == "repeat"
    assert len(pending) == 1
    assert pending[0]["repeat_count"] == 2
    assert pending[0]["target_time"] > past_dt.strftime("%Y-%m-%d %H:%M:%S")


def test_check_due_tasks_once_preserves_invalid_time(tmp_path, monkeypatch):
    import core.heartbeat as heartbeat
    import core.tools.builtins as builtins

    task_file = tmp_path / "tasks.json"
    monkeypatch.setattr(builtins, "TASKS_FILE", task_file)
    task_file.write_text(
        json.dumps([{"id": "bad", "target_time": "invalid", "description": "bad"}]),
        encoding="utf-8",
    )

    assert heartbeat.check_due_tasks_once() == []
    pending = json.loads(task_file.read_text(encoding="utf-8"))
    assert pending[0]["id"] == "bad"

