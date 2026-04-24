"""
评测相关 API 路由
"""
from typing import Optional

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.eval import (
    DashboardStats,
    EvaluationListResponse,
    EvaluationRequest,
    EvaluationResponse,
)
from app.services.eval_service import EvalService
from app.core.config import get_settings

router = APIRouter(prefix="/eval", tags=["evaluation"])


@router.post("/run", response_model=EvaluationResponse)
async def run_evaluation(
    request: EvaluationRequest,
    db: AsyncSession = Depends(get_db),
) -> EvaluationResponse:
    """运行评测"""
    service = EvalService(db)
    return await service.run_evaluation(request)


@router.get("", response_model=EvaluationListResponse)
async def list_evaluations(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
) -> EvaluationListResponse:
    """获取评测列表"""
    service = EvalService(db)
    return await service.list_evaluations(page, page_size)


@router.get("/report/latest")
async def get_latest_eval_report() -> dict[str, Any]:
    """读取 deterministic/live 脚本生成的 latest.json 报告。"""
    settings = get_settings()
    report_path = Path(settings.data_dir) / "eval_reports" / "latest.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Latest evaluation report not found")
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to read latest report: {exc}") from exc


@router.get("/{eval_id}", response_model=EvaluationResponse)
async def get_evaluation(
    eval_id: str,
    db: AsyncSession = Depends(get_db),
) -> EvaluationResponse:
    """获取评测详情"""
    service = EvalService(db)
    result = await service.get_evaluation(eval_id)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return result


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    """获取 Dashboard 统计"""
    service = EvalService(db)
    return await service.get_dashboard_stats()


@router.delete("/{eval_id}")
async def delete_evaluation(
    eval_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """删除评测结果"""
    service = EvalService(db)
    success = await service.delete_evaluation(eval_id)
    return {"success": success}
