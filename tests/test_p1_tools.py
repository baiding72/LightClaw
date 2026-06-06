#!/usr/bin/env python3
"""P1 Tools Test Suite for myClaw.

Run with: PYTHONPATH=/Users/baiding/LightClaw python tests/test_p1_tools.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.tools.builtins import (
    ALL_TOOLS,
    save_note, search_notes, read_note,
    save_user_profile, read_user_profile,
    get_system_info,
    schedule_task, list_tasks, cancel_task, modify_task,
)

passed = 0
failed = 0


def run_tool_case(name, tool, args, expected_contains=None):
    global passed, failed
    print(f"\n--- {name} ---")
    try:
        result = tool.invoke(args) if isinstance(args, dict) else tool.invoke(**args)
        result_str = str(result)
        print(f"Result: {result_str[:200]}")

        if expected_contains:
            if any(exp in result_str for exp in expected_contains):
                print(f"  ✓ Contains: {expected_contains}")
                passed += 1
            else:
                print(f"  ✗ Missing: {expected_contains}")
                failed += 1
        else:
            print(f"  ✓ OK")
            passed += 1
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        failed += 1
    return result_str


def main():
    global passed, failed

    print("=" * 60)
    print("myClaw P1 Tools Test Suite")
    print("=" * 60)

    tool_map = {t.name: t for t in ALL_TOOLS}

    # ==========================================
    # P1: Task Scheduling Tools
    # ==========================================
    print("\n--- Task Scheduling ---")

    # schedule_task
    future_time = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    run_tool_case("schedule_task", tool_map["schedule_task"],
              {"target_time": future_time, "description": "Test task"},
              expected_contains=["Task scheduled", "at "])

    # schedule_task with repeat
    run_tool_case("schedule_task (daily)", tool_map["schedule_task"],
              {"target_time": future_time, "description": "Daily reminder", "repeat": "daily", "repeat_count": 3},
              expected_contains=["repeat: daily"])

    # list_tasks
    result = run_tool_case("list_tasks", tool_map["list_tasks"], {},
                       expected_contains=["Pending tasks"])
    print(f"  Current tasks: {result.count('- [') + result.count('- [')} task(s) listed")

    # modify_task
    import json
    tasks_file = Path.home() / ".myclaw" / "tasks" / "tasks.json"
    if tasks_file.exists():
        tasks = json.loads(tasks_file.read_text())
        if tasks:
            task_id = tasks[0]["id"]
            run_tool_case("modify_task", tool_map["modify_task"],
                      {"task_id": task_id, "new_description": "Modified task"},
                      expected_contains=["updated"])
            # cancel it
            run_tool_case("cancel_task", tool_map["cancel_task"],
                      {"task_id": task_id},
                      expected_contains=["cancelled"])
        else:
            print("  (no tasks to modify/cancel)")
    else:
        print("  (no tasks file)")

    print("\n  list_tasks after cleanup:")
    print(f"  {tool_map['list_tasks'].invoke({})}")

    # ==========================================
    # P1: Note/Memory Tools
    # ==========================================
    print("\n--- Note/Memory Tools ---")

    # save_note
    run_tool_case("save_note", tool_map["save_note"],
              {"content": "This is a test note for P1 testing.", "title": "P1 Test Note"},
              expected_contains=["Note saved"])

    # search_notes
    run_tool_case("search_notes", tool_map["search_notes"],
              {"keyword": "P1 Test"},
              expected_contains=["Found"])

    # read_user_profile
    run_tool_case("save_user_profile", tool_map["save_user_profile"],
              {"new_content": "# Test Profile\nLanguage: English\nTheme: Dark"},
              expected_contains=["updated"])

    run_tool_case("read_user_profile", tool_map["read_user_profile"],
              {},
              expected_contains=["Test Profile"])

    # ==========================================
    # P1: System Info
    # ==========================================
    print("\n--- System Info ---")

    result = run_tool_case("get_system_info", tool_map["get_system_info"], {},
                       expected_contains=["OS:", "Python:"])
    print(f"  Info: {result.replace(chr(10), ' | ')}")

    # ==========================================
    # Summary
    # ==========================================
    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
