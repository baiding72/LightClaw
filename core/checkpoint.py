"""Turn-level checkpointing for crash and interruption recovery."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import RUNTIME_DIR


CHECKPOINT_DIR = RUNTIME_DIR / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


def checkpoint_path(session_id: str) -> Path:
    return CHECKPOINT_DIR / f"{session_id}.json"


def write_checkpoint(session_id: str, **fields: Any) -> Path:
    path = checkpoint_path(session_id)
    payload = {
        "session_id": session_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def read_checkpoint(session_id: str) -> dict[str, Any] | None:
    path = checkpoint_path(session_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def clear_checkpoint(session_id: str) -> None:
    checkpoint_path(session_id).unlink(missing_ok=True)
