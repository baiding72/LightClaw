"""Lazy SKILL.md loader with help -> run two-stage execution."""

from __future__ import annotations

from dataclasses import dataclass, field
import fnmatch
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


def _matches_tool_pattern(patterns: list[str], tool_name: str) -> bool:
    return any(fnmatch.fnmatch(tool_name, pattern) for pattern in patterns)


def _format_metadata_summary(skill_info: dict[str, Any]) -> str:
    rows = []
    for key in ["trigger", "do_not_trigger", "argument_hint"]:
        value = skill_info.get(key)
        if value:
            rows.append(f"- {key}: {value}")
    for key in ["allowed_tools", "blocked_tools", "tags"]:
        value = skill_info.get(key) or []
        if value:
            rows.append(f"- {key}: {', '.join(value)}")
    rows.append(f"- user_invocable: {bool(skill_info.get('user_invocable', True))}")
    rows.append(f"- disable_auto_invoke: {bool(skill_info.get('disable_auto_invoke', False))}")
    return "Metadata:\n" + "\n".join(rows)


@dataclass(frozen=True)
class SkillManifest:
    folder: str
    md_path: str
    mtime: float
    raw_name: str
    name: str
    description: str
    trigger: str = ""
    do_not_trigger: str = ""
    user_invocable: bool = True
    disable_auto_invoke: bool = False
    allowed_tools: list[str] = field(default_factory=list)
    blocked_tools: list[str] = field(default_factory=list)
    argument_hint: str = ""
    tags: list[str] = field(default_factory=list)

    def metadata(self) -> dict[str, Any]:
        return {
            "raw_name": self.raw_name,
            "trigger": self.trigger,
            "do_not_trigger": self.do_not_trigger,
            "user_invocable": self.user_invocable,
            "disable_auto_invoke": self.disable_auto_invoke,
            "allowed_tools": list(self.allowed_tools),
            "blocked_tools": list(self.blocked_tools),
            "argument_hint": self.argument_hint,
            "tags": list(self.tags),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "folder": self.folder,
            "md_path": self.md_path,
            "mtime": self.mtime,
            "raw_name": self.raw_name,
            "name": self.name,
            "description": self.description,
            **self.metadata(),
        }


class SkillRegistry:
    """Scan skill metadata and cache parsed manifests."""

    def __init__(self, skills_dir: Path | None = None, scan_interval: int = 60) -> None:
        self._skills_dir = skills_dir
        self._manifests: list[SkillManifest] | None = None
        self._last_scan_time = 0.0
        self._scan_interval = scan_interval

    @property
    def skills_dir(self) -> Path:
        return self._skills_dir or SKILLS_DIR

    def list_manifests(self, force_rescan: bool = False) -> list[SkillManifest]:
        now = time.time()
        if (
            not force_rescan
            and self._manifests is not None
            and now - self._last_scan_time < self._scan_interval
        ):
            return self._manifests

        manifests: list[SkillManifest] = []
        skills_dir = self.skills_dir
        if not skills_dir.exists():
            self._manifests = []
            self._last_scan_time = now
            return []

        for folder in sorted(skills_dir.iterdir(), key=lambda path: path.name.lower()):
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
            manifests.append(
                SkillManifest(
                    folder=folder.name,
                    md_path=str(md_path),
                    mtime=md_path.stat().st_mtime,
                    **metadata,
                )
            )

        self._manifests = manifests
        self._last_scan_time = now
        return manifests

    def get_manifest(self, name: str) -> SkillManifest | None:
        for manifest in self.list_manifests():
            if manifest.name == name:
                return manifest
        return None

    def reload(self) -> list[SkillManifest]:
        self.clear_cache()
        return self.list_manifests(force_rescan=True)

    def clear_cache(self) -> None:
        self._manifests = None
        self._last_scan_time = 0.0

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


class LazySkillLoader:
    """Expose skill manifests as lazy tools that load manuals on `mode='help'`."""

    def __init__(self, cache_size: int = 50, scan_interval: int = 60, registry: SkillRegistry | None = None) -> None:
        self.registry = registry or SkillRegistry(scan_interval=scan_interval)
        self._cache_size = cache_size

    @lru_cache(maxsize=50)
    def _load_skill_content(self, md_path: str, mtime: float) -> str:
        return Path(md_path).read_text(encoding="utf-8", errors="replace")

    def _create_lazy_tool(self, manifest: SkillManifest) -> FunctionTool:
        skill_info = manifest.as_dict()

        def lazy_runner(mode: str, command: str = "") -> str:
            normalized_mode = (mode or "").strip().lower()
            if normalized_mode == "help":
                skill_content = self._load_skill_content(str(skill_info["md_path"]), float(skill_info["mtime"]))
                metadata_summary = _format_metadata_summary(skill_info)
                return (
                    f"========== [{skill_info['raw_name']} manual] ==========\n"
                    f"{metadata_summary}\n\n"
                    f"{skill_content[:3000]}\n"
                    f"====================================\n"
                    "If this skill fits the task, call this same tool again with mode='run' "
                    "and a concrete non-interactive command. Use {baseDir} for the skill directory."
                )
            if normalized_mode == "run":
                if not command or not command.strip():
                    return "Error: command is required when mode='run'."
                run_backend = "execute_office_shell"
                blocked_tools = list(skill_info.get("blocked_tools") or [])
                allowed_tools = list(skill_info.get("allowed_tools") or [])
                if _matches_tool_pattern(blocked_tools, run_backend):
                    return f"Error: this skill blocks {run_backend} via blocked-tools."
                if allowed_tools and not _matches_tool_pattern(allowed_tools, run_backend):
                    return f"Error: this skill allowed-tools does not include {run_backend}."
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
        tool.skill_metadata = manifest.metadata()
        return tool

    def get_all_tools(self, force_rescan: bool = False) -> list[FunctionTool]:
        return [self._create_lazy_tool(manifest) for manifest in self.registry.list_manifests(force_rescan=force_rescan)]

    def get_tool_count(self) -> int:
        return len(self.registry.list_manifests())

    def clear_cache(self) -> None:
        self._load_skill_content.cache_clear()
        self.registry.clear_cache()


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
