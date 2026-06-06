"""myClaw tools package - Custom implementation."""

from core.tools.base import BaseTool, tool
from core.tools.builtins import ALL_TOOLS
from core.tools.files import FILE_TOOLS
from core.tools.shell import SHELL_TOOLS
from core.skill_loader import load_dynamic_skills

# Combined all tools for convenience
ALL_TOOLS = ALL_TOOLS + FILE_TOOLS + SHELL_TOOLS + load_dynamic_skills()

__all__ = ["BaseTool", "tool", "ALL_TOOLS"]
