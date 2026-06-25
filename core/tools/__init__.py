"""myClaw tools package - Custom implementation."""

from core.tools.base import BaseTool, tool
from core.tools.builtins import ALL_TOOLS as BUILTIN_TOOLS
from core.tools.files import FILE_TOOLS
from core.tools.shell import SHELL_TOOLS


class _AllTools(list):
    """Combined built-in and dynamic tools, with dynamic skills loaded lazily."""

    def __init__(self) -> None:
        super().__init__(BUILTIN_TOOLS + FILE_TOOLS + SHELL_TOOLS)
        self._dynamic_loaded = False

    def _ensure_dynamic(self) -> None:
        if self._dynamic_loaded:
            return
        from core.skill_loader import load_dynamic_skills

        self.extend(load_dynamic_skills())
        self._dynamic_loaded = True

    def __iter__(self):
        self._ensure_dynamic()
        return super().__iter__()

    def __len__(self) -> int:
        self._ensure_dynamic()
        return super().__len__()

    def __getitem__(self, index):
        self._ensure_dynamic()
        return super().__getitem__(index)


# Combined all tools for convenience.
ALL_TOOLS = _AllTools()

__all__ = ["BaseTool", "tool", "ALL_TOOLS"]
