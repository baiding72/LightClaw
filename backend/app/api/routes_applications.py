"""
求职申请跟踪 API
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.job_application import (
    ApplicationCreate,
    ApplicationListResponse,
    ApplicationResponse,
    ApplicationUpdate,
)
from app.services.application_service import ApplicationService

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=ApplicationListResponse)
async def list_applications(
    status: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> ApplicationListResponse:
    service = ApplicationService(db)
    return await service.list_applications(status=status, limit=limit)


@router.post("", response_model=ApplicationResponse)
async def create_application(
    payload: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    service = ApplicationService(db)
    return await service.create_application(payload)


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: str,
    payload: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    service = ApplicationService(db)
    updated = await service.update_application(application_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return updated
