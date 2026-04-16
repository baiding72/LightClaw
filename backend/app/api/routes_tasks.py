"""
任务相关 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TaskStatus
from app.db import get_db
from app.schemas.task import (
    TaskRunRequest,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskSummary,
    TaskUpdate,
)
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse)
async def create_task(
    task_create: TaskCreate,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """创建新任务"""
    service = TaskService(db)
    return await service.create_task(task_create)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    page: int = 1,
    page_size: int = 20,
    status: str = None,
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    """获取任务列表"""
    service = TaskService(db)
    return await service.list_tasks(page, page_size, status)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """获取任务详情"""
    service = TaskService(db)
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/run")
async def run_task(
    task_id: str,
    run_request: TaskRunRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """运行任务"""
    service = TaskService(db)
    result = await service.run_task(
        task_id,
        browser_context=run_request.browser_context if run_request else None,
    )
    return result


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """更新任务"""
    service = TaskService(db)
    task = await service.update_task(task_id, task_update)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """删除任务"""
    service = TaskService(db)
    success = await service.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "message": "Task deleted"}


@router.get("/built-in/list")
async def list_built_in_tasks() -> list[dict]:
    """列出内置任务"""
    from app.tasks.definitions import ALL_TASKS
    return [
        {
            "task_id": t.task_id,
            "instruction": t.instruction,
            "category": t.category.value,
            "difficulty": t.difficulty.value,
            "allowed_tools": t.allowed_tools,
        }
        for t in ALL_TASKS
    ]
