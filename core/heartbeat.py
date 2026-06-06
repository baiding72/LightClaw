"""Heartbeat task pacemaker for myClaw."""

from __future__ import annotations

import asyncio
import calendar
import json
from datetime import datetime, timedelta
from typing import Any

import core.tools.builtins as builtins


def _parse_task_time(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _next_repeat_time(target_dt: datetime, repeat: str) -> datetime | None:
    if repeat == "hourly":
        return target_dt + timedelta(hours=1)
    if repeat == "daily":
        return target_dt + timedelta(days=1)
    if repeat == "weekly":
        return target_dt + timedelta(days=7)
    if repeat == "monthly":
        month = target_dt.month + 1
        year = target_dt.year
        if month > 12:
            month = 1
            year += 1
        last_day = calendar.monthrange(year, month)[1]
        return target_dt.replace(year=year, month=month, day=min(target_dt.day, last_day))
    return None


def format_trigger_message(task: dict[str, Any]) -> str:
    return (
        "[myClaw heartbeat]\n"
        "A scheduled task is due. Remind the user or continue the requested action.\n"
        f"Task: {task.get('description', '')}"
    )


def check_due_tasks_once(now: datetime | None = None) -> list[dict[str, Any]]:
    """Trigger due tasks once and rewrite the pending task file.

    Returns the triggered task dictionaries. Repeating tasks are rescheduled;
    one-shot due tasks are removed.
    """
    now = now or datetime.now()
    task_file = builtins.TASKS_FILE
    if not task_file.exists():
        return []

    with builtins._TASKS_LOCK:
        try:
            content = task_file.read_text(encoding="utf-8").strip()
            tasks = json.loads(content) if content else []
        except Exception:
            return []
        if not isinstance(tasks, list):
            return []

        pending: list[dict[str, Any]] = []
        triggered: list[dict[str, Any]] = []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            target_dt = _parse_task_time(str(task.get("target_time", "")))
            if target_dt is None:
                pending.append(task)
                continue
            if now < target_dt:
                pending.append(task)
                continue

            triggered.append(dict(task))
            repeat = task.get("repeat")
            if not repeat:
                continue
            repeat_count = task.get("repeat_count")
            if repeat_count is not None:
                try:
                    repeat_count = int(repeat_count)
                except (TypeError, ValueError):
                    repeat_count = None
                if repeat_count is not None:
                    if repeat_count <= 1:
                        continue
                    task["repeat_count"] = repeat_count - 1
            next_dt = _next_repeat_time(target_dt, str(repeat))
            if next_dt is None:
                continue
            while next_dt <= now:
                maybe_next = _next_repeat_time(next_dt, str(repeat))
                if maybe_next is None:
                    break
                next_dt = maybe_next
            task["target_time"] = next_dt.strftime("%Y-%m-%d %H:%M:%S")
            pending.append(task)

        if triggered:
            task_file.parent.mkdir(parents=True, exist_ok=True)
            task_file.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")
        return triggered


async def pacemaker_loop(task_queue: asyncio.Queue, check_interval: int = 10) -> None:
    """Background loop that emits due tasks into an async queue."""
    while True:
        await asyncio.sleep(check_interval)
        for task in check_due_tasks_once():
            await task_queue.put(format_trigger_message(task))
