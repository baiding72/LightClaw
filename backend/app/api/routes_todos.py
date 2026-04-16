from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import TodoModel, get_db

router = APIRouter(prefix="/todos", tags=["todos"])


@router.get("")
async def list_todos(
    limit: int = 20,
    status: str = "all",
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(TodoModel).order_by(TodoModel.created_at.desc()).limit(limit)
    if status != "all":
        query = query.where(TodoModel.status == status)

    result = await db.execute(query)
    todos = result.scalars().all()

    return {
        "todos": [
            {
                "id": todo.id,
                "title": todo.title,
                "description": todo.description,
                "deadline": todo.deadline.isoformat() if todo.deadline else None,
                "priority": todo.priority,
                "status": todo.status,
                "created_at": todo.created_at.isoformat(),
                "updated_at": todo.updated_at.isoformat(),
            }
            for todo in todos
        ],
        "total": len(todos),
    }
