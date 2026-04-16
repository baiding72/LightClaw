from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import NoteModel, get_db

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("")
async def list_notes(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(NoteModel).order_by(NoteModel.created_at.desc()).limit(limit)
    )
    notes = result.scalars().all()

    return {
        "notes": [
            {
                "id": note.id,
                "title": note.title,
                "content": note.content,
                "created_at": note.created_at.isoformat(),
                "updated_at": note.updated_at.isoformat(),
            }
            for note in notes
        ],
        "total": len(notes),
    }
