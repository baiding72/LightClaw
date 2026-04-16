"""
数据池服务
"""
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SampleType, TrajectoryType
from app.db.models import DataPoolSampleModel
from app.schemas.datapool import (
    DataPoolFilter,
    DataPoolListResponse,
    DataPoolSampleResponse,
    DataPoolStats,
    ExportRequest,
    ExportResponse,
)


class DataPoolService:
    """数据池服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_samples(
        self,
        page: int = 1,
        page_size: int = 20,
        sample_type: Optional[str] = None,
        trajectory_type: Optional[str] = None,
    ) -> DataPoolListResponse:
        """获取样本列表"""
        query = select(DataPoolSampleModel)

        if sample_type:
            query = query.where(DataPoolSampleModel.sample_type == sample_type)
        if trajectory_type:
            query = query.where(DataPoolSampleModel.trajectory_type == trajectory_type)

        # 计算总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页
        query = query.order_by(DataPoolSampleModel.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        samples = result.scalars().all()

        return DataPoolListResponse(
            samples=[self._to_response(s) for s in samples],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_sample(self, sample_id: str) -> Optional[dict]:
        """获取样本详情"""
        result = await self.db.execute(
            select(DataPoolSampleModel).where(DataPoolSampleModel.sample_id == sample_id)
        )
        sample = result.scalar_one_or_none()
        if not sample:
            return None
        return self._to_response(sample).model_dump()

    async def get_stats(self) -> DataPoolStats:
        """获取数据池统计"""
        # 总数
        total_result = await self.db.execute(
            select(func.count()).select_from(DataPoolSampleModel)
        )
        total = total_result.scalar() or 0

        # 按类型统计
        by_type = {}
        for sample_type in SampleType:
            result = await self.db.execute(
                select(func.count()).where(DataPoolSampleModel.sample_type == sample_type.value)
            )
            by_type[sample_type.value] = result.scalar() or 0

        # 按轨迹类型统计
        by_trajectory_type = {}
        for traj_type in TrajectoryType:
            result = await self.db.execute(
                select(func.count()).where(DataPoolSampleModel.trajectory_type == traj_type.value)
            )
            by_trajectory_type[traj_type.value] = result.scalar() or 0

        # 导出状态
        exported_result = await self.db.execute(
            select(func.count()).where(DataPoolSampleModel.is_exported == True)
        )
        exported = exported_result.scalar() or 0

        return DataPoolStats(
            total_samples=total,
            by_type=by_type,
            by_trajectory_type=by_trajectory_type,
            by_failure_type={},
            exported_count=exported,
            unexported_count=total - exported,
        )

    async def export_samples(self, request: ExportRequest) -> ExportResponse:
        """导出样本"""
        from app.datapool import DataPoolExporter

        # 获取样本
        query = select(DataPoolSampleModel)
        if not request.include_exported:
            query = query.where(DataPoolSampleModel.is_exported == False)
        if request.sample_types:
            query = query.where(DataPoolSampleModel.sample_type.in_([st.value for st in request.sample_types]))

        result = await self.db.execute(query)
        samples = result.scalars().all()

        # 转换为字典
        sample_dicts = [self._to_response(s).model_dump() for s in samples]

        # 导出
        exporter = DataPoolExporter()
        file_path = exporter.export_all(sample_dicts)

        # 更新导出状态
        for sample in samples:
            sample.is_exported = True
        await self.db.commit()

        return ExportResponse(
            export_id=f"export_{uuid.uuid4().hex[:8]}",
            file_path=str(file_path.get("tool_use", "")),
            total_samples=len(samples),
            sample_types={},
            created_at=datetime.now(),
        )

    async def build_from_trajectories(self) -> dict:
        """从轨迹构建样本"""
        from app.datapool import DataPoolBuilder
        from app.gateway import TrajectoryPersistence
        from app.core.config import get_settings

        settings = get_settings()
        persistence = TrajectoryPersistence(settings.trajectories_dir)
        builder = DataPoolBuilder()

        trajectories = persistence.list_trajectories()
        total_samples = 0

        for traj_info in trajectories:
            try:
                traj_data = persistence.load_trajectory(traj_info["path"])
                # TODO: 转换为 Trajectory 对象并构建样本
                total_samples += 1
            except Exception as e:
                continue

        return {
            "success": True,
            "trajectories_processed": len(trajectories),
            "samples_created": total_samples,
        }

    async def delete_sample(self, sample_id: str) -> bool:
        """删除样本"""
        result = await self.db.execute(
            select(DataPoolSampleModel).where(DataPoolSampleModel.sample_id == sample_id)
        )
        sample = result.scalar_one_or_none()
        if not sample:
            return False

        await self.db.delete(sample)
        await self.db.commit()
        return True

    def _to_response(self, sample: DataPoolSampleModel) -> DataPoolSampleResponse:
        """转换为响应模型"""
        return DataPoolSampleResponse(
            sample_id=sample.sample_id,
            sample_type=sample.sample_type,
            trajectory_type=sample.trajectory_type,
            task_id=sample.task_id,
            step_ids=sample.step_ids or [],
            failure_type=sample.failure_type,
            content=sample.content or {},
            screenshot_paths=sample.screenshot_paths,
            is_exported=sample.is_exported,
            created_at=sample.created_at,
        )
