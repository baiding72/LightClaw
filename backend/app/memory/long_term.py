"""
长期记忆实现
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import json
from pathlib import Path


@dataclass
class LongTermMemory:
    """
    长期记忆

    持久化存储跨任务的信息
    """

    # 存储路径
    storage_path: Optional[str] = None

    # 记忆项字典
    items: dict[str, dict[str, Any]] = field(default_factory=dict)

    # 创建时间
    created_at: datetime = field(default_factory=datetime.now)

    def add(
        self,
        key: str,
        value: Any,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """添加长期记忆"""
        self.items[key] = {
            "key": key,
            "value": value,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        # 持久化
        self._persist()

    def get(self, key: str) -> Optional[Any]:
        """获取长期记忆"""
        if key in self.items:
            return self.items[key]["value"]
        return None

    def get_all(self) -> dict[str, dict[str, Any]]:
        """获取所有长期记忆"""
        return self.items.copy()

    def update(self, key: str, value: Any) -> bool:
        """更新长期记忆"""
        if key in self.items:
            self.items[key]["value"] = value
            self.items[key]["updated_at"] = datetime.now().isoformat()
            self._persist()
            return True
        return False

    def delete(self, key: str) -> bool:
        """删除长期记忆"""
        if key in self.items:
            del self.items[key]
            self._persist()
            return True
        return False

    def clear(self) -> None:
        """清空所有长期记忆"""
        self.items.clear()
        self._persist()

    def search(self, query: str) -> list[dict[str, Any]]:
        """简单文本搜索"""
        results = []
        query_lower = query.lower()
        for item in self.items.values():
            if (
                query_lower in str(item["key"]).lower()
                or query_lower in str(item["value"]).lower()
            ):
                results.append(item)
        return results

    def keys(self) -> list[str]:
        """获取所有键"""
        return list(self.items.keys())

    def _persist(self) -> None:
        """持久化到文件"""
        if self.storage_path:
            try:
                path = Path(self.storage_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({
                        "items": self.items,
                        "created_at": self.created_at.isoformat(),
                    }, f, ensure_ascii=False, indent=2)
            except Exception as e:
                # 静默失败
                pass

    def _load(self) -> None:
        """从文件加载"""
        if self.storage_path:
            try:
                path = Path(self.storage_path)
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.items = data.get("items", {})
                        if "created_at" in data:
                            self.created_at = datetime.fromisoformat(data["created_at"])
            except Exception as e:
                # 静默失败
                pass

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "storage_path": self.storage_path,
            "items": self.items,
            "created_at": self.created_at.isoformat(),
            "count": len(self.items),
        }

    @classmethod
    def from_storage(cls, storage_path: str) -> "LongTermMemory":
        """从存储创建"""
        memory = cls(storage_path=storage_path)
        memory._load()
        return memory
