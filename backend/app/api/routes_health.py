"""
健康检查 API 路由
"""
from fastapi import APIRouter

from app.llm import ChatMessage, get_llm_adapter
from app.tools import get_tool_registry

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """健康检查"""
    return {
        "status": "healthy",
        "service": "lightclaw",
    }


@router.get("/health/llm")
async def llm_health_check() -> dict:
    """LLM 健康检查"""
    llm = get_llm_adapter()

    try:
        response = await llm.chat(
            [ChatMessage(role="user", content="Reply with OK only.")],
            max_tokens=8,
            temperature=0,
        )
        return {
            "status": "healthy",
            "model": llm.model_name,
            "response": response.content.strip(),
            "latency_ms": response.latency_ms,
        }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "model": llm.model_name,
            "error": str(exc),
        }


@router.get("/tools")
async def list_tools() -> dict:
    """列出所有可用工具"""
    registry = get_tool_registry()
    return {
        "tools": registry.get_tool_infos(),
        "total": len(registry.get_all()),
    }


@router.get("/tools/{tool_name}")
async def get_tool_info(tool_name: str) -> dict:
    """获取工具详情"""
    registry = get_tool_registry()
    tool = registry.get(tool_name)
    if not tool:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Tool not found")

    return {
        "name": tool.name,
        "description": tool.description,
        "category": tool.category,
        "parameters": [p.model_dump() for p in tool.parameters],
        "schema": tool.get_openai_schema(),
    }
