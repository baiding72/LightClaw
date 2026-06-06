"""CyberClaw built-in tool tests migrated to myClaw tool names and outputs."""

from __future__ import annotations

import json
from datetime import datetime, timedelta


def test_get_time_format():
    from core.tools.builtins import get_time

    result = get_time.invoke({})
    parsed = datetime.strptime(result, "%Y-%m-%d %H:%M:%S")

    assert isinstance(parsed, datetime)


def test_calculator_valid_and_invalid_expressions():
    from core.tools.builtins import calculator

    assert calculator.invoke({"expression": "2 + 3"}) == "5"
    assert calculator.invoke({"expression": "10 * 5"}) == "50"
    assert "Error" in calculator.invoke({"expression": "2 +"})
    assert "Error" in calculator.invoke({"expression": "__import__('os')"})


def test_save_user_profile_merges_with_temp_file(tmp_path, monkeypatch):
    import core.tools.builtins as builtins

    profile_path = tmp_path / "profile.md"
    monkeypatch.setattr(builtins, "PROFILE_FILE", profile_path)

    initial = "# User Profile\n- Language: Chinese"
    assert "User profile saved" in builtins.save_user_profile.invoke({"new_content": initial})
    assert profile_path.read_text(encoding="utf-8") == initial

    update = builtins.save_user_profile.invoke({"new_content": "- Answer style: concise"})
    assert "User profile updated" in update
    assert "Answer style" in profile_path.read_text(encoding="utf-8")


def test_scheduled_task_crud_with_temp_file(tmp_path, monkeypatch):
    import core.tools.builtins as builtins

    task_file = tmp_path / "tasks.json"
    monkeypatch.setattr(builtins, "TASKS_DIR", tmp_path)
    monkeypatch.setattr(builtins, "TASKS_FILE", task_file)

    target_time = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    result = builtins.schedule_task.invoke({"target_time": target_time, "description": "drink water"})
    assert "Task scheduled" in result

    tasks = json.loads(task_file.read_text(encoding="utf-8"))
    task_id = tasks[0]["id"]

    listed = builtins.list_tasks.invoke({})
    assert "drink water" in listed

    updated = builtins.modify_task.invoke({"task_id": task_id, "new_description": "drink tea"})
    assert "updated" in updated
    assert "drink tea" in builtins.list_tasks.invoke({})

    cancelled = builtins.cancel_task.invoke({"task_id": task_id})
    assert "cancelled" in cancelled
    assert "No scheduled tasks" in builtins.list_tasks.invoke({})


def test_schedule_task_invalid_time_with_temp_file(tmp_path, monkeypatch):
    import core.tools.builtins as builtins

    monkeypatch.setattr(builtins, "TASKS_DIR", tmp_path)
    monkeypatch.setattr(builtins, "TASKS_FILE", tmp_path / "tasks.json")

    assert "time format" in builtins.schedule_task.invoke({"target_time": "invalid_time", "description": "bad"})
    assert "future" in builtins.schedule_task.invoke({"target_time": "2020-01-01 00:00:00", "description": "past"})


def test_get_system_info_mentions_runtime():
    from core.tools.builtins import get_system_info

    result = get_system_info.invoke({})

    assert "OS:" in result
    assert "Python:" in result
