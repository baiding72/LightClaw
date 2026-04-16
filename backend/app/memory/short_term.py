"""
短期记忆实现
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
import json


@dataclass
class ShortTermMemory:
    """
    短期记忆

    存储当前任务执行过程中的临时信息
    """

    # 记忆容量限制
    max_items: int = 100

    # 记忆项列表
    items: list[dict[str, Any]] = field(default_factory=list)

    # 创建时间
    created_at: datetime = field(default_factory=datetime.now)

    def add(
        self,
        key: str,
        value: Any,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """添加记忆项"""
        item = {
            "key": key,
            "value": value,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
        }

        self.items.append(item)

        # 超出容量时移除最旧的
        if len(self.items) > self.max_items:
            self.items = self.items[-self.max_items:]

    def get(self, key: str) -> Optional[Any]:
        """获取记忆项"""
        for item in reversed(self.items):
            if item["key"] == key:
                return item["value"]
        return None

    def get_all(self, key: Optional[str] = None) -> list[dict[str, Any]]:
        """获取所有匹配的记忆项"""
        if key is None:
            return self.items.copy()
        return [item for item in self.items if item["key"] == key]

    def update(self, key: str, value: Any) -> bool:
        """更新记忆项"""
        for item in reversed(self.items):
            if item["key"] == key:
                item["value"] = value
                item["updated_at"] = datetime.now().isoformat()
                return True
        return False

    def delete(self, key: str) -> bool:
        """删除记忆项"""
        for i, item in enumerate(self.items):
            if item["key"] == key:
                self.items.pop(i)
                return True
        return False

    def clear(self) -> None:
        """清空所有记忆"""
        self.items.clear()

    def get_recent(self, n: int = 10) -> list[dict[str, Any]]:
        """获取最近的 n 条记忆"""
        return self.items[-n:]

    def search(self, query: str) -> list[dict[str, Any]]:
        """简单文本搜索"""
        results = []
        query_lower = query.lower()
        for item in self.items:
            if (
                query_lower in str(item["key"]).lower()
                or query_lower in str(item["value"]).lower()
            ):
                results.append(item)
        return results

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "max_items": self.max_items,
            "items": self.items,
            "created_at": self.created_at.isoformat(),
            "count": len(self.items),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ShortTermMemory":
        """从字典创建"""
        return cls(
            max_items=data.get("max_items", 100),
            items=data.get("items", []),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
        )
