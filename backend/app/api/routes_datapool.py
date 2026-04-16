"""
数据池相关 API 路由
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.datapool import (
    DataPoolListResponse,
    DataPoolStats,
    ExportRequest,
    ExportResponse,
)
from app.services.datapool_service import DataPoolService

router = APIRouter(prefix="/datapool", tags=["datapool"])


@router.get("", response_model=DataPoolListResponse)
async def list_samples(
    page: int = 1,
    page_size: int = 20,
    sample_type: str = None,
    trajectory_type: str = None,
    db: AsyncSession = Depends(get_db),
) -> DataPoolListResponse:
    """获取数据池样本列表"""
    service = DataPoolService(db)
    return await service.list_samples(page, page_size, sample_type, trajectory_type)


@router.get("/stats", response_model=DataPoolStats)
async def get_stats(
    db: AsyncSession = Depends(get_db),
) -> DataPoolStats:
    """获取数据池统计"""
    service = DataPoolService(db)
    return await service.get_stats()


@router.get("/{sample_id}")
async def get_sample(
    sample_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取样本详情"""
    service = DataPoolService(db)
    sample = await service.get_sample(sample_id)
    if not sample:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Sample not found")
    return sample


@router.post("/export", response_model=ExportResponse)
async def export_samples(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:
    """导出样本"""
    service = DataPoolService(db)
    return await service.export_samples(request)


@router.post("/build")
async def build_from_trajectories(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """从轨迹构建样本"""
    service = DataPoolService(db)
    result = await service.build_from_trajectories()
    return result


@router.delete("/{sample_id}")
async def delete_sample(
    sample_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """删除样本"""
    service = DataPoolService(db)
    success = await service.delete_sample(sample_id)
    return {"success": success}
