"""Deterministic skill selector for progressive tool loading."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.tools.registry import ToolRegistry


@dataclass(frozen=True)
class SkillSelection:
    selected_skills: list[str]
    allowed_tools: list[str]
    reasons: dict[str, str]


class SkillSelector:
    """Selects coarse tool skills before exposing concrete tools to the planner."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def select(
        self,
        instruction: str,
        *,
        browser_context: dict[str, Any] | None = None,
        scenario_type: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> SkillSelection:
        if allowed_tools:
            return self._select_from_allowed_tools(allowed_tools)

        lowered = instruction.lower()
        selected: list[str] = []
        reasons: dict[str, str] = {}

        def add(skill_id: str, reason: str) -> None:
            if skill_id not in selected and self.registry.get_skill(skill_id):
                selected.append(skill_id)
                reasons[skill_id] = reason

        if browser_context and browser_context.get("selected_tab"):
            add("browser_gui_control", "任务带有选中浏览器标签页，需要 GUI/页面观察工具。")

        if scenario_type == "recruiting" or any(
            keyword in lowered for keyword in ["招聘", "投递", "岗位", "申请", "resume", "job", "career"]
        ):
            add("information_retrieval", "招聘/投递任务需要先读取和抽取已有页面或轨迹信息。")
            if browser_context:
                add("browser_gui_control", "招聘页面任务可能需要浏览器观察或安全 dry-run。")

        if any(keyword in lowered for keyword in ["写", "记录", "总结", "note", "笔记"]):
            add("structured_memory_write", "任务要求写入笔记或总结产物。")

        if any(keyword in lowered for keyword in ["待办", "提醒", "todo", "reminder", "日程", "calendar"]):
            add("structured_memory_write", "任务要求创建结构化待办/日程。")

        if any(keyword in lowered for keyword in ["apple", "mac", "提醒事项", "备忘录", "本机"]):
            add("apple_native_apps", "任务明确要求写入或展示 macOS 原生应用。")

        if any(keyword in lowered for keyword in ["计算", "calculate", "math", "加", "减", "乘", "除"]):
            add("utility_reasoning", "任务包含确定性计算。")

        if not selected:
            add("information_retrieval", "默认先加载轻量读取工具，避免暴露全部工具。")
            add("structured_memory_write", "保留最小内部产物写入能力。")

        return SkillSelection(
            selected_skills=selected,
            allowed_tools=self._expand_tools(selected),
            reasons=reasons,
        )

    def _select_from_allowed_tools(self, allowed_tools: list[str]) -> SkillSelection:
        skills: list[str] = []
        reasons: dict[str, str] = {}
        for skill in self.registry.list_skills():
            tool_names = set(skill["tool_names"])
            if any(tool_name in tool_names for tool_name in allowed_tools):
                skill_id = skill["skill_id"]
                skills.append(skill_id)
                reasons[skill_id] = "由显式 allowed_tools 反推得到。"
        return SkillSelection(selected_skills=skills, allowed_tools=allowed_tools, reasons=reasons)

    def _expand_tools(self, selected_skills: list[str]) -> list[str]:
        tools: list[str] = []
        for skill_id in selected_skills:
            skill = self.registry.get_skill(skill_id)
            if not skill:
                continue
            for tool_name in skill.tool_names:
                if tool_name not in tools:
                    tools.append(tool_name)
        return tools
