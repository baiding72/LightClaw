"""Lazy SKILL.md loader with help -> run two-stage execution."""

from __future__ import annotations

from functools import lru_cache
import re
import time
from pathlib import Path
from typing import Any

from core.config import SKILLS_DIR
from core.tools.base import FunctionTool
from core.tools.shell import execute_office_shell


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


class LazySkillLoader:
    """Scan skill metadata eagerly, load full manuals only on `mode='help'`."""

    def __init__(self, cache_size: int = 50, scan_interval: int = 60) -> None:
        self._skill_registry: list[dict[str, Any]] | None = None
        self._last_scan_time = 0.0
        self._scan_interval = scan_interval
        self._cache_size = cache_size

    @lru_cache(maxsize=50)
    def _load_skill_content(self, md_path: str, mtime: float) -> str:
        return Path(md_path).read_text(encoding="utf-8", errors="replace")

    def _scan_skills(self, force_rescan: bool = False) -> list[dict[str, Any]]:
        now = time.time()
        if (
            not force_rescan
            and self._skill_registry is not None
            and now - self._last_scan_time < self._scan_interval
        ):
            return self._skill_registry

        skills: list[dict[str, Any]] = []
        if not SKILLS_DIR.exists():
            self._skill_registry = []
            self._last_scan_time = now
            return []

        for folder in sorted(SKILLS_DIR.iterdir(), key=lambda path: path.name.lower()):
            if not folder.is_dir():
                continue
            md_path = folder / "SKILL.md"
            if not md_path.exists():
                md_path = folder / "README.md"
            if not md_path.exists():
                continue
            metadata = self._extract_metadata(md_path)
            if not metadata:
                continue
            skills.append(
                {
                    "folder": folder.name,
                    "md_path": str(md_path),
                    "mtime": md_path.stat().st_mtime,
                    **metadata,
                }
            )

        self._skill_registry = skills
        self._last_scan_time = now
        return skills

    def _extract_metadata(self, md_path: Path) -> dict[str, Any] | None:
        try:
            lines = md_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return None

        fields: dict[str, Any] = {}
        if lines and lines[0].strip() == "---":
            current_key: str | None = None
            current_items: list[str] = []
            for raw in lines[1:]:
                if raw.strip() == "---":
                    if current_key:
                        fields[current_key] = current_items
                    break
                if raw.startswith("  - ") and current_key:
                    current_items.append(raw[4:].strip().strip("\"'"))
                    continue
                if ":" not in raw:
                    continue
                if current_key:
                    fields[current_key] = current_items
                    current_key = None
                    current_items = []
                key, value = raw.split(":", 1)
                key = key.strip()
                value = value.strip().strip("\"'")
                if value:
                    fields[key] = value
                else:
                    current_key = key
                    current_items = []
        else:
            content = "\n".join(lines[:50])
            for key in ("name", "description"):
                match = re.search(rf"^{key}:\s*(.+)$", content, re.MULTILINE)
                if match:
                    fields[key] = match.group(1).strip().strip("\"'")

        raw_name = str(fields.get("name") or md_path.parent.name).strip("\"'")
        raw_name = raw_name.strip("\"'")
        tool_name = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_name).strip("_") or md_path.parent.name
        raw_desc = str(fields.get("description") or f"Provides {raw_name} skill functions.").strip("\"'")
        return {
            "raw_name": raw_name,
            "name": tool_name,
            "description": raw_desc,
            "trigger": str(fields.get("trigger") or ""),
            "do_not_trigger": str(fields.get("do-not-trigger") or fields.get("do_not_trigger") or ""),
            "user_invocable": _parse_bool(fields.get("user-invocable", fields.get("user_invocable")), True),
            "disable_auto_invoke": _parse_bool(fields.get("disable-auto-invoke", fields.get("disable_auto_invoke")), False),
            "allowed_tools": _parse_list(fields.get("allowed-tools", fields.get("allowed_tools"))),
            "blocked_tools": _parse_list(fields.get("blocked-tools", fields.get("blocked_tools"))),
            "argument_hint": str(fields.get("argument-hint") or fields.get("argument_hint") or ""),
            "tags": _parse_list(fields.get("tags")),
        }

    def _create_lazy_tool(self, skill_info: dict[str, Any]) -> FunctionTool:
        def lazy_runner(mode: str, command: str = "") -> str:
            normalized_mode = (mode or "").strip().lower()
            if normalized_mode == "help":
                skill_content = self._load_skill_content(str(skill_info["md_path"]), float(skill_info["mtime"]))
                return (
                    f"========== [{skill_info['raw_name']} manual] ==========\n"
                    f"{skill_content[:3000]}\n"
                    f"====================================\n"
                    "If this skill fits the task, call this same tool again with mode='run' "
                    "and a concrete non-interactive command. Use {baseDir} for the skill directory."
                )
            if normalized_mode == "run":
                if not command or not command.strip():
                    return "Error: command is required when mode='run'."
                actual_cmd = command.replace("{baseDir}", f"skills/{skill_info['folder']}")
                return execute_office_shell.invoke({"command": actual_cmd})
            return "Error: mode must be 'help' or 'run'."

        parameters = {
            "properties": {
                "mode": {
                    "type": "string",
                    "description": "Must be 'help' or 'run'. First use should be 'help'.",
                },
                "command": {
                    "type": "string",
                    "description": "Required for mode='run'. Use {baseDir} for this skill folder.",
                },
            },
            "required": ["mode"],
        }
        description_parts = [str(skill_info["description"])]
        if skill_info.get("trigger"):
            description_parts.append(f"Trigger: {skill_info['trigger']}")
        if skill_info.get("do_not_trigger"):
            description_parts.append(f"Do not trigger: {skill_info['do_not_trigger']}")
        description_parts.append(f"User-invocable: {bool(skill_info.get('user_invocable', True))}")
        description_parts.append(
            "External skill. First call mode='help' to read the full SKILL.md manual; "
            "then call mode='run' with command only if the manual fits the task."
        )
        description = "\n\n".join(description_parts)
        tool = FunctionTool(
            lazy_runner,
            name=str(skill_info["name"]),
            description=description,
            parameters=parameters,
        )
        tool.skill_metadata = {
            key: skill_info[key]
            for key in [
                "raw_name",
                "trigger",
                "do_not_trigger",
                "user_invocable",
                "disable_auto_invoke",
                "allowed_tools",
                "blocked_tools",
                "argument_hint",
                "tags",
            ]
        }
        return tool

    def get_all_tools(self, force_rescan: bool = False) -> list[FunctionTool]:
        return [self._create_lazy_tool(info) for info in self._scan_skills(force_rescan=force_rescan)]

    def get_tool_count(self) -> int:
        return len(self._scan_skills())

    def clear_cache(self) -> None:
        self._load_skill_content.cache_clear()
        self._skill_registry = None
        self._last_scan_time = 0.0


_lazy_loader = LazySkillLoader()


def load_dynamic_skills(force_rescan: bool = False) -> list[FunctionTool]:
    return _lazy_loader.get_all_tools(force_rescan=force_rescan)


def reload_skills() -> list[FunctionTool]:
    _lazy_loader.clear_cache()
    return _lazy_loader.get_all_tools(force_rescan=True)


def get_skill_count() -> int:
    return _lazy_loader.get_tool_count()


def clear_skill_cache() -> None:
    _lazy_loader.clear_cache()
