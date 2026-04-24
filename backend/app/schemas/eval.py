"""
评测相关 Schema
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class EvaluationMetrics(BaseModel):
    """评测指标"""
    task_success_rate: float = Field(..., ge=0.0, le=1.0)
    tool_execution_success_rate: float = Field(..., ge=0.0, le=1.0)
    recovery_rate: float = Field(..., ge=0.0, le=1.0)
    gui_action_accuracy: float = Field(..., ge=0.0, le=1.0)
    invalid_tool_call_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    wrong_args_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    policy_violation_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_steps: float = 0.0
    avg_latency_ms: float
    total_token_cost: float = 0.0


class TaskEvaluationDetail(BaseModel):
    """单个任务评测详情"""
    task_id: str
    instruction: str
    is_success: bool
    steps_count: int
    tool_calls_count: int
    gui_actions_count: int
    failure_types: list[str]
    recovery_attempts: int
    successful_recoveries: int
    latency_ms: int
    token_usage: Optional[dict[str, int]] = None


class EvaluationRequest(BaseModel):
    """评测请求"""
    eval_name: str
    mode: str = "deterministic"
    task_ids: Optional[list[str]] = None  # None 表示运行所有任务
    categories: Optional[list[str]] = None
    difficulties: Optional[list[str]] = None


class EvaluationResponse(BaseModel):
    """评测响应"""
    eval_id: str
    eval_name: str
    total_tasks: int
    metrics: EvaluationMetrics
    details: list[TaskEvaluationDetail]
    created_at: datetime

    class Config:
        from_attributes = True


class EvaluationSummary(BaseModel):
    """评测摘要"""
    eval_id: str
    eval_name: str
    total_tasks: int
    task_success_rate: float
    tool_execution_success_rate: float
    recovery_rate: float
    gui_action_accuracy: float
    created_at: datetime


class EvaluationListResponse(BaseModel):
    """评测列表响应"""
    evaluations: list[EvaluationSummary]
    total: int
    page: int
    page_size: int


class FailureDistribution(BaseModel):
    """失败类型分布"""
    failure_type: str
    count: int
    percentage: float


class DashboardStats(BaseModel):
    """Dashboard 统计数据"""
    total_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    task_success_rate: float
    recent_failures: list[FailureDistribution]
    total_samples: int
    recent_evaluations: list[EvaluationSummary]
