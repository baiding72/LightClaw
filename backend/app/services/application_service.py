"""
求职申请跟踪服务
"""
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApplicationModel
from app.scenarios import detect_job_site_profile
from app.schemas.job_application import (
    ApplicationCreate,
    ApplicationListResponse,
    ApplicationResponse,
    ApplicationUpdate,
)


class ApplicationService:
    """申请记录服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _build_metadata(self, payload_metadata: dict | None, source_url: str | None) -> dict:
        metadata = dict(payload_metadata or {})
        profile = detect_job_site_profile(source_url)
        if profile:
            metadata.setdefault(
                "site_profile",
                {
                    "site_key": profile.site_key,
                    "display_name": profile.display_name,
                },
            )
        return metadata

    async def create_application(self, payload: ApplicationCreate) -> ApplicationResponse:
        metadata = self._build_metadata(payload.metadata, payload.source_url)
        application = ApplicationModel(
            application_id=f"app_{uuid.uuid4().hex[:8]}",
            company_name=payload.company_name,
            role_title=payload.role_title,
            status=payload.status,
            source_url=payload.source_url,
            location=payload.location,
            notes=payload.notes,
            next_action=payload.next_action,
            application_metadata=metadata,
        )
        self.db.add(application)
        await self.db.commit()
        await self.db.refresh(application)
        return self._to_response(application)

    async def list_applications(
        self,
        *,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> ApplicationListResponse:
        query = select(ApplicationModel)
        count_query = select(func.count()).select_from(ApplicationModel)

        if status:
            query = query.where(ApplicationModel.status == status)
            count_query = count_query.where(ApplicationModel.status == status)

        query = query.order_by(ApplicationModel.updated_at.desc()).limit(limit)
        result = await self.db.execute(query)
        count_result = await self.db.execute(count_query)
        applications = result.scalars().all()
        total = count_result.scalar() or 0

        return ApplicationListResponse(
            applications=[self._to_response(item) for item in applications],
            total=total,
        )

    async def update_application(
        self,
        application_id: str,
        payload: ApplicationUpdate,
    ) -> Optional[ApplicationResponse]:
        result = await self.db.execute(
            select(ApplicationModel).where(ApplicationModel.application_id == application_id)
        )
        application = result.scalar_one_or_none()
        if application is None:
            return None

        if payload.status is not None:
            application.status = payload.status
        if payload.source_url is not None:
            application.source_url = payload.source_url
        if payload.location is not None:
            application.location = payload.location
        if payload.notes is not None:
            application.notes = payload.notes
        if payload.next_action is not None:
            application.next_action = payload.next_action
        if payload.metadata is not None:
            application.application_metadata = self._build_metadata(payload.metadata, application.source_url)
        elif payload.source_url is not None:
            application.application_metadata = self._build_metadata(
                application.application_metadata,
                application.source_url,
            )

        await self.db.commit()
        await self.db.refresh(application)
        return self._to_response(application)

    def _to_response(self, application: ApplicationModel) -> ApplicationResponse:
        return ApplicationResponse(
            application_id=application.application_id,
            company_name=application.company_name,
            role_title=application.role_title,
            status=application.status,
            source_url=application.source_url,
            location=application.location,
            notes=application.notes,
            next_action=application.next_action,
            metadata=application.application_metadata or {},
            created_at=application.created_at,
            updated_at=application.updated_at,
        )
