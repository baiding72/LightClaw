"""Runtime configuration helpers for myClaw."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MYCLAW_DIR = PROJECT_ROOT
WORKSPACE_DIR = MYCLAW_DIR / "workspace"
OFFICE_DIR = WORKSPACE_DIR / "office"
SKILLS_DIR = OFFICE_DIR / "skills"
BUILTIN_SKILLS_DIR = MYCLAW_DIR / "skills" / "builtin"
MEMORY_DIR = WORKSPACE_DIR / "memory"
TASKS_DIR = Path.home() / ".myclaw" / "tasks"
TASKS_FILE = TASKS_DIR / "tasks.json"
CONFIG_DIR = MYCLAW_DIR / "config"
POLICY_CONFIG_FILE = CONFIG_DIR / "policy.json"
RUNTIME_DIR = MYCLAW_DIR / "runtime"
APPROVALS_DIR = RUNTIME_DIR / "approvals"


for directory in [WORKSPACE_DIR, OFFICE_DIR, SKILLS_DIR, BUILTIN_SKILLS_DIR, MEMORY_DIR, CONFIG_DIR, RUNTIME_DIR, APPROVALS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


DEFAULT_POLICY_CONFIG = {
    "mode": "off",
    "approval_timeout_seconds": 300,
}


def load_policy_config() -> dict[str, Any]:
    if not POLICY_CONFIG_FILE.exists():
        return dict(DEFAULT_POLICY_CONFIG)
    try:
        data = json.loads(POLICY_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_POLICY_CONFIG)
    config = dict(DEFAULT_POLICY_CONFIG)
    if isinstance(data, dict):
        config.update(data)
    return config


def save_policy_config(config: dict[str, Any]) -> dict[str, Any]:
    next_config = dict(DEFAULT_POLICY_CONFIG)
    next_config.update(config)
    mode = str(next_config.get("mode", "off")).lower()
    mode = {
        "monitor": "auto",
        "enforce": "default",
        "ask": "default",
        "read_only": "plan",
    }.get(mode, mode)
    if mode not in {"off", "default", "plan", "auto"}:
        mode = "off"
    next_config["mode"] = mode
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    POLICY_CONFIG_FILE.write_text(json.dumps(next_config, ensure_ascii=False, indent=2), encoding="utf-8")
    return next_config
