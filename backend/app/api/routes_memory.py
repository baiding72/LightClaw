"""
记忆相关 API 路由
"""
from fastapi import APIRouter

from app.memory import MemoryManager

router = APIRouter(prefix="/memory", tags=["memory"])

# 全局记忆管理器
_memory_manager = MemoryManager()


@router.get("")
async def get_memory() -> dict:
    """获取所有记忆"""
    return _memory_manager.get_all_memories()


@router.get("/short-term")
async def get_short_term_memory() -> dict:
    """获取短期记忆"""
    return _memory_manager.short_term.to_dict()


@router.get("/long-term")
async def get_long_term_memory() -> dict:
    """获取长期记忆"""
    return _memory_manager.long_term.to_dict()


@router.post("/short-term")
async def add_short_term_memory(
    key: str,
    value: str,
) -> dict:
    """添加短期记忆"""
    _memory_manager.add_short_term(key, value)
    return {"success": True, "message": "Short-term memory added"}


@router.post("/long-term")
async def add_long_term_memory(
    key: str,
    value: str,
) -> dict:
    """添加长期记忆"""
    _memory_manager.add_long_term(key, value)
    return {"success": True, "message": "Long-term memory added"}


@router.delete("/short-term/{key}")
async def delete_short_term_memory(key: str) -> dict:
    """删除短期记忆"""
    success = _memory_manager.short_term.delete(key)
    return {"success": success}


@router.delete("/long-term/{key}")
async def delete_long_term_memory(key: str) -> dict:
    """删除长期记忆"""
    success = _memory_manager.long_term.delete(key)
    return {"success": success}


@router.delete("/short-term")
async def clear_short_term_memory() -> dict:
    """清空短期记忆"""
    _memory_manager.clear_short_term()
    return {"success": True, "message": "Short-term memory cleared"}


@router.delete("/long-term")
async def clear_long_term_memory() -> dict:
    """清空长期记忆"""
    _memory_manager.clear_long_term()
    return {"success": True, "message": "Long-term memory cleared"}


@router.get("/search")
async def search_memory(query: str) -> dict:
    """搜索记忆"""
    return _memory_manager.search(query)
