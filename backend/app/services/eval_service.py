"""
评测服务
"""
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import FailureType
from app.db.models import EvaluationResultModel, TaskModel
from app.schemas.eval import (
    DashboardStats,
    EvaluationListResponse,
    EvaluationRequest,
    EvaluationResponse,
    EvaluationSummary,
    FailureDistribution,
)


class EvalService:
    """评测服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_evaluation(self, request: EvaluationRequest) -> EvaluationResponse:
        """运行评测"""
        from app.eval import EvaluationRunner

        runner = EvaluationRunner()
        result = await runner.run_evaluation(
            eval_name=request.eval_name,
            task_ids=request.task_ids,
            categories=request.categories,
            difficulties=request.difficulties,
        )

        # 保存到数据库
        eval_model = EvaluationResultModel(
            eval_id=result.eval_id,
            eval_name=result.eval_name,
            total_tasks=result.total_tasks,
            task_success_rate=result.metrics.task_success_rate,
            tool_execution_success_rate=result.metrics.tool_execution_success_rate,
            recovery_rate=result.metrics.recovery_rate,
            gui_action_accuracy=result.metrics.gui_action_accuracy,
            avg_latency_ms=result.metrics.avg_latency_ms,
            total_token_cost=result.metrics.total_token_cost,
            details={
                "details": [d.model_dump() for d in result.details],
            },
        )

        self.db.add(eval_model)
        await self.db.commit()

        return result

    async def get_evaluation(self, eval_id: str) -> Optional[EvaluationResponse]:
        """获取评测详情"""
        result = await self.db.execute(
            select(EvaluationResultModel).where(EvaluationResultModel.eval_id == eval_id)
        )
        eval_model = result.scalar_one_or_none()
        if not eval_model:
            return None

        return self._to_response(eval_model)

    async def list_evaluations(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> EvaluationListResponse:
        """获取评测列表"""
        query = select(EvaluationResultModel)

        # 计算总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页
        query = query.order_by(EvaluationResultModel.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        evaluations = result.scalars().all()

        return EvaluationListResponse(
            evaluations=[self._to_summary(e) for e in evaluations],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_dashboard_stats(self) -> DashboardStats:
        """获取 Dashboard 统计"""
        # 任务统计
        total_tasks_result = await self.db.execute(
            select(func.count()).select_from(TaskModel)
        )
        total_tasks = total_tasks_result.scalar() or 0

        running_tasks_result = await self.db.execute(
            select(func.count()).where(TaskModel.status == "running")
        )
        running_tasks = running_tasks_result.scalar() or 0

        completed_tasks_result = await self.db.execute(
            select(func.count()).where(TaskModel.status == "completed")
        )
        completed_tasks = completed_tasks_result.scalar() or 0

        failed_tasks_result = await self.db.execute(
            select(func.count()).where(TaskModel.status == "failed")
        )
        failed_tasks = failed_tasks_result.scalar() or 0

        # 成功率
        success_rate = completed_tasks / total_tasks if total_tasks > 0 else 0.0

        # 最近失败分布
        recent_failures = []
        for failure_type in FailureType:
            # 简化实现
            recent_failures.append(FailureDistribution(
                failure_type=failure_type.value,
                count=0,
                percentage=0.0,
            ))

        # 最近评测
        evals_result = await self.db.execute(
            select(EvaluationResultModel).order_by(EvaluationResultModel.created_at.desc()).limit(5)
        )
        recent_evals = evals_result.scalars().all()

        return DashboardStats(
            total_tasks=total_tasks,
            running_tasks=running_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            task_success_rate=success_rate,
            recent_failures=recent_failures,
            total_samples=0,  # TODO
            recent_evaluations=[self._to_summary(e) for e in recent_evals],
        )

    async def delete_evaluation(self, eval_id: str) -> bool:
        """删除评测结果"""
        result = await self.db.execute(
            select(EvaluationResultModel).where(EvaluationResultModel.eval_id == eval_id)
        )
        eval_model = result.scalar_one_or_none()
        if not eval_model:
            return False

        await self.db.delete(eval_model)
        await self.db.commit()
        return True

    def _to_response(self, eval_model: EvaluationResultModel) -> EvaluationResponse:
        """转换为响应模型"""
        from app.schemas.eval import EvaluationMetrics, TaskEvaluationDetail

        details = eval_model.details.get("details", []) if eval_model.details else []

        return EvaluationResponse(
            eval_id=eval_model.eval_id,
            eval_name=eval_model.eval_name,
            total_tasks=eval_model.total_tasks,
            metrics=EvaluationMetrics(
                task_success_rate=eval_model.task_success_rate,
                tool_execution_success_rate=eval_model.tool_execution_success_rate,
                recovery_rate=eval_model.recovery_rate,
                gui_action_accuracy=eval_model.gui_action_accuracy,
                avg_latency_ms=eval_model.avg_latency_ms,
                total_token_cost=eval_model.total_token_cost,
            ),
            details=[TaskEvaluationDetail(**d) for d in details],
            created_at=eval_model.created_at,
        )

    def _to_summary(self, eval_model: EvaluationResultModel) -> EvaluationSummary:
        """转换为摘要模型"""
        return EvaluationSummary(
            eval_id=eval_model.eval_id,
            eval_name=eval_model.eval_name,
            total_tasks=eval_model.total_tasks,
            task_success_rate=eval_model.task_success_rate,
            tool_execution_success_rate=eval_model.tool_execution_success_rate,
            recovery_rate=eval_model.recovery_rate,
            gui_action_accuracy=eval_model.gui_action_accuracy,
            created_at=eval_model.created_at,
        )
