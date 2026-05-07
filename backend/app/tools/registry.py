"""
工具注册表
"""

from app.core.logger import logger
from app.schemas.tool import ToolInfo
from app.tools.base import BaseTool
from app.tools.skills import ToolSkill, build_default_tool_skills


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._categories: dict[str, list[str]] = {}
        self._skills: dict[str, ToolSkill] = {}
        self._tool_to_skill: dict[str, str] = {}

    def register(self, tool: BaseTool) -> None:
        """注册工具"""
        self._tools[tool.name] = tool

        if tool.category not in self._categories:
            self._categories[tool.category] = []
        self._categories[tool.category].append(tool.name)

        logger.info(f"Registered tool: {tool.name} in category: {tool.category}")

    def register_skill(self, skill: ToolSkill) -> None:
        """注册 skill 元数据，不立即实例化工具。"""
        self._skills[skill.skill_id] = skill
        for tool_name in skill.tool_names:
            self._tool_to_skill[tool_name] = skill.skill_id
        logger.info(
            "Registered tool skill: %s (%s tools)",
            skill.skill_id,
            len(skill.tool_names),
        )

    def load_skill(self, skill_id: str) -> list[BaseTool]:
        """按需加载某个 skill 下的工具。"""
        skill = self._skills.get(skill_id)
        if not skill:
            return []
        if skill.loaded:
            return [self._tools[name] for name in skill.tool_names if name in self._tools]

        loaded_tools = []
        for tool in skill.load_tools():
            self.register(tool)
            loaded_tools.append(tool)
        return loaded_tools

    def load_all_skills(self) -> None:
        """加载所有 skill。用于兼容旧的全量工具列表行为。"""
        for skill_id in list(self._skills):
            self.load_skill(skill_id)

    def list_skills(self) -> list[dict]:
        """返回 skill 元数据；不触发工具加载。"""
        return [
            {
                "skill_id": skill.skill_id,
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
                "trigger_hints": skill.trigger_hints,
                "tool_names": skill.tool_names,
                "loaded": skill.loaded,
            }
            for skill in self._skills.values()
        ]

    def get_skill(self, skill_id: str) -> ToolSkill | None:
        return self._skills.get(skill_id)

    def get_loaded_tool_count(self) -> int:
        return len(self._tools)

    def get(self, name: str) -> BaseTool | None:
        """获取工具"""
        if name not in self._tools and name in self._tool_to_skill:
            self.load_skill(self._tool_to_skill[name])
        return self._tools.get(name)

    def get_all(self) -> list[BaseTool]:
        """获取所有工具"""
        self.load_all_skills()
        return list(self._tools.values())

    def get_by_category(self, category: str) -> list[BaseTool]:
        """按类别获取工具"""
        for skill in self._skills.values():
            if skill.category == category:
                self.load_skill(skill.skill_id)
        tool_names = self._categories.get(category, [])
        return [self._tools[name] for name in tool_names]

    def get_schemas(self, tool_names: list[str] | None = None) -> list[dict]:
        """获取工具 Schema 列表"""
        if tool_names is None:
            self.load_all_skills()
            return [tool.get_openai_schema() for tool in self._tools.values()]

        schemas = []
        for name in tool_names:
            tool = self.get(name)
            if tool:
                schemas.append(tool.get_openai_schema())
        return schemas

    def get_tool_infos(self) -> list[ToolInfo]:
        """获取工具信息列表"""
        self.load_all_skills()
        infos = []
        for tool in self._tools.values():
            params_summary = ", ".join(
                f"{p.name}" + ("*" if p.required else "")
                for p in tool.parameters
            )
            infos.append(ToolInfo(
                name=tool.name,
                description=tool.description,
                category=tool.category,
                parameters_summary=params_summary or "无参数",
            ))
        return infos

    def list_tools(self) -> list[str]:
        """列出所有工具名称"""
        return list(self._tool_to_skill.keys())

    def has_tool(self, name: str) -> bool:
        """检查工具是否存在"""
        return name in self._tools or name in self._tool_to_skill


# 全局工具注册表
_tool_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """获取工具注册表单例"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
        # 注册默认工具
        _register_default_tools(_tool_registry)
    return _tool_registry


def _register_default_tools(registry: ToolRegistry) -> None:
    """注册默认 skill 元数据，工具按需渐进式加载。"""
    for skill in build_default_tool_skills():
        registry.register_skill(skill)
