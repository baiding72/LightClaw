"""
记忆管理器

整合短期记忆和长期记忆
"""
from typing import Any, Optional
from pathlib import Path

from app.core.config import get_settings
from app.memory.short_term import ShortTermMemory
from app.memory.long_term import LongTermMemory


class MemoryManager:
    """
    记忆管理器

    管理短期记忆和长期记忆的统一接口
    """

    def __init__(self, storage_dir: Optional[str] = None):
        self.settings = get_settings()
        self.storage_dir = storage_dir or self.settings.data_dir

        # 初始化记忆存储
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory(
            storage_path=str(Path(self.storage_dir) / "memory" / "long_term.json")
        )

    def add_short_term(
        self,
        key: str,
        value: Any,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """添加短期记忆"""
        self.short_term.add(key, value, metadata)

    def add_long_term(
        self,
        key: str,
        value: Any,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """添加长期记忆"""
        self.long_term.add(key, value, metadata)

    def get(self, key: str, long_term: bool = False) -> Optional[Any]:
        """
        获取记忆

        优先从短期记忆获取，如果找不到且 long_term=True，则从长期记忆获取
        """
        value = self.short_term.get(key)
        if value is not None:
            return value
        if long_term:
            return self.long_term.get(key)
        return None

    def update(
        self,
        key: str,
        value: Any,
        long_term: bool = False,
    ) -> bool:
        """更新记忆"""
        if long_term:
            return self.long_term.update(key, value)
        return self.short_term.update(key, value)

    def delete(self, key: str, long_term: bool = False) -> bool:
        """删除记忆"""
        if long_term:
            return self.long_term.delete(key)
        return self.short_term.delete(key)

    def clear_short_term(self) -> None:
        """清空短期记忆"""
        self.short_term.clear()

    def clear_long_term(self) -> None:
        """清空长期记忆"""
        self.long_term.clear()

    def clear_all(self) -> None:
        """清空所有记忆"""
        self.short_term.clear()
        self.long_term.clear()

    def search(self, query: str) -> dict[str, list[dict[str, Any]]]:
        """搜索记忆"""
        return {
            "short_term": self.short_term.search(query),
            "long_term": self.long_term.search(query),
        }

    def get_context_for_task(self, task_id: str) -> dict[str, Any]:
        """
        获取任务相关的上下文

        从记忆中提取与当前任务相关的信息
        """
        context = {
            "task_id": task_id,
            "short_term": self.short_term.get_recent(10),
            "long_term": {},
        }

        # 获取相关的长期记忆
        for key in ["user_preferences", "common_patterns", "previous_tasks"]:
            value = self.long_term.get(key)
            if value:
                context["long_term"][key] = value

        return context

    def get_all_memories(self) -> dict[str, Any]:
        """获取所有记忆"""
        return {
            "short_term": self.short_term.to_dict(),
            "long_term": self.long_term.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "short_term": self.short_term.to_dict(),
            "long_term": self.long_term.to_dict(),
        }
