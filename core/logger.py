"""Small JSONL audit logger for myClaw harness experiments - Custom implementation."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_DIR = PROJECT_ROOT / "runs"


class RunLogger:
    """Append-only JSONL logger used by interactive runs and evals."""

    def __init__(
        self,
        run_id: str | None = None,
        runs_dir: str | os.PathLike[str] | None = None,
        enabled: bool = True,
    ) -> None:
        self.enabled = enabled
        self.run_id = run_id or self._new_run_id()
        self.runs_dir = Path(runs_dir) if runs_dir is not None else DEFAULT_RUNS_DIR
        self.path = self.runs_dir / f"{self.run_id}.jsonl"

        if self.enabled:
            self.runs_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _new_run_id() -> str:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{stamp}-{uuid4().hex[:8]}"

    def log_event(self, event: str, **fields: Any) -> None:
        if not self.enabled:
            return

        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "event": event,
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


class NullLogger:
    """Logger with the same interface that intentionally records nothing."""

    enabled = False
    run_id = "disabled"
    path = None

    def log_event(self, event: str, **fields: Any) -> None:
        return


def message_preview(content: Any, limit: int = 160) -> str:
    text = "" if content is None else str(content)
    text = text.replace("\n", "\\n")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def summarize_messages(messages: list[Any]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for message in messages:
        item = {
            "type": type(message).__name__,
            "content_preview": message_preview(getattr(message, "content", "")),
        }
        name = getattr(message, "name", None)
        if name:
            item["name"] = name
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            item["tool_calls"] = [
                {
                    "name": tool_call.get("name"),
                    "args": tool_call.get("args"),
                    "id": tool_call.get("id"),
                }
                for tool_call in tool_calls
            ]
        summary.append(item)
    return summary
